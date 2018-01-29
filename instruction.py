import struct
import math
from collections import defaultdict
from functools import lru_cache
from enum import Enum

from settings import getSetting


"""
Tools to encode and decode instructions.

To add a new instruction, one must:
1) Add it into the exportInstrInfo dictionary (see further down), with its type;
2) Add a token for it in tokenizer (or extend an existing token) in tokenizer.py, ensuring that the token regexp is
    unique and do not pick up other tokens;
3) Add a yacc rule to parse it (or extend an existing one) in yaccparser.py and ensure that the rule does not
    clash with others;
4) Update BytecodeToInstrInfos() (see further down) so it is able to _decode_ this instruction from bytecode;
5) Update Simulator.decodeInstr() in procsimulator.py so it can decode the new instruction and display a meaningful
    message describing its behavior;
6) Update Simulator.execInstr() in procsimulator.py so it can execute the new instruction correctly, including all of
    its side effects (flags, memory change, etc.)
7) Add a test case in tests/bytecodeTest.asm and update tests/bytecodeObj.o with a new version of the bytecode
    synchronized with the new bytecodeTest.asm (use IAR for this purpose). Ensure all unit tests pass.
"""

class InstrType(Enum):
    undefined = -1
    dataop = 0
    memop = 1
    multiplememop = 2
    branch = 3
    multiply = 4
    swap = 5
    softinterrupt = 6
    psrtransfer = 7
    shiftop = 8
    nopop = 9
    otherop = 10
    multiplylong = 11
    declareOp = 100


exportInstrInfo = {# DATA OPERATIONS
                   'AND': InstrType.dataop,
                   'EOR': InstrType.dataop,
                   'SUB': InstrType.dataop,
                   'RSB': InstrType.dataop,
                   'ADD': InstrType.dataop,
                   'ADC': InstrType.dataop,
                   'SBC': InstrType.dataop,
                   'RSC': InstrType.dataop,
                   'TST': InstrType.dataop,
                   'TEQ': InstrType.dataop,
                   'CMP': InstrType.dataop,
                   'CMN': InstrType.dataop,
                   'ORR': InstrType.dataop,
                   'MOV': InstrType.dataop,
                   'BIC': InstrType.dataop,
                   'MVN': InstrType.dataop,
                    # The next five are not actual operations, but can be translated to a MOV op
                   'LSR': InstrType.shiftop,
                   'LSL': InstrType.shiftop,
                   'ASR': InstrType.shiftop,
                   'ROR': InstrType.shiftop,
                   'RRX': InstrType.shiftop,
                    # PROGRAM STATUS REGISTER OPERATIONS
                   'MRS': InstrType.psrtransfer,
                   'MSR': InstrType.psrtransfer,
                    # MEMORY OPERATIONS
                   'LDR': InstrType.memop,
                   'STR': InstrType.memop,
                    # MULTIPLE MEMORY OPERATIONS
                   'LDM': InstrType.multiplememop,
                   'STM': InstrType.multiplememop,
                   'PUSH': InstrType.multiplememop,
                   'POP': InstrType.multiplememop,
                    # BRANCH OPERATIONS
                   'B'  : InstrType.branch,
                   'BX' : InstrType.branch,
                   'BL' : InstrType.branch,
                   'BLX': InstrType.branch,
                    # MULTIPLY OPERATIONS
                   'MUL': InstrType.multiply,
                   'MLA': InstrType.multiply,
                    # MULTIPLY OPERATIONS LONG
                   'UMULL': InstrType.multiplylong,
                   'UMLAL': InstrType.multiplylong,
                   'SMULL': InstrType.multiplylong,
                   'SMLAL': InstrType.multiplylong,
                    # SWAP OPERATIONS
                   'SWP': InstrType.swap,
                    # SOFTWARE INTERRUPT OPERATIONS
                   'SWI': InstrType.softinterrupt,
                   'SVC': InstrType.softinterrupt,      # Same opcode, but two different mnemonics
                    # NOP
                   'NOP': InstrType.nopop,
                   }

globalInstrInfo = dict(exportInstrInfo)
globalInstrInfo.update({# DECLARATION STATEMENTS
                   'DC' : InstrType.declareOp,
                   'DS' : InstrType.declareOp,
                    })

conditionMapping = {'EQ': 0,
                    'NE': 1,
                    'CS': 2,
                    'CC': 3,
                    'MI': 4,
                    'PL': 5,
                    'VS': 6,
                    'VC': 7,
                    'HI': 8,
                    'LS': 9,
                    'GE': 10,
                    'LT': 11,
                    'GT': 12,
                    'LE': 13,
                    'AL': 14}

conditionMappingR = {v: k for k,v in conditionMapping.items()}

shiftMapping = {'LSL': 0,
                'LSR': 1,
                'ASR': 2,
                'ROR': 3,
                'RRX': 3}

shiftMappingR = {0: 'LSL', 1: 'LSR', 2: 'ASR', 3: 'ROR'}

updateModeLDMMapping = {'ED': 3, 'IB': 3,
                        'FD': 1, 'IA': 1,
                        'EA': 2, 'DB': 2,
                        'FA': 0, 'DA': 0}
updateModeSTMMapping = {'FA': 3, 'IB': 3,
                        'EA': 1, 'IA': 1,
                        'FD': 2, 'DB': 2,
                        'ED': 0, 'DA': 0}

dataOpcodeMapping = {'AND': 0,
                     'EOR': 1,
                     'SUB': 2,
                     'RSB': 3,
                     'ADD': 4,
                     'ADC': 5,
                     'SBC': 6,
                     'RSC': 7,
                     'TST': 8,
                     'TEQ': 9,
                     'CMP': 10,
                     'CMN': 11,
                     'ORR': 12,
                     'MOV': 13,
                     'BIC': 14,
                     'MVN': 15}

dataOpcodeInvert = {'MOV': 'MVN', 'MVN': 'MOV',
                    'ADD': 'SUB', 'SUB': 'ADD',
                    'AND': 'BIC', 'BIC': 'AND',
                    'CMP': 'CMN', 'CMN': 'CMP'}

dataOpcodeMappingR = {v: k for k,v in dataOpcodeMapping.items()}

def immediateToBytecode(imm, mode=None, alreadyinverted=False, gccMode=True):
    """
    The immediate operand rotate field is a 4 bit unsigned integer which specifies a shift
    operation on the 8 bit immediate value. This value is zero extended to 32 bits, and then
    subject to a rotate right by twice the value in the rotate field. (ARM datasheet, 4.5.3)

    GCC and IAR have different ways of dealing with immediate rotate:
    IAR put the constant to the far left of the unsigned field (that is, it uses as many rotations as possible)
    GCC put the constant to the far right of the unsigned field (using as few rotations as possible)
    :param imm:
    :return:
    """
    def tryInvert():
        if mode is None:
            return None
        if mode == 'logical':
            invimm = (~imm) & 0xFFFFFFFF
        elif mode == 'arithmetic':
            invimm = (~imm + 1) & 0xFFFFFFFF
        ret2 = immediateToBytecode(invimm, mode, True)
        if ret2:
            return ret2[0], ret2[1], True
        return None

    imm &= 0xFFFFFFFF
    if imm == 0:
        return 0, 0, False
    if imm < 256:
        return imm, 0, False

    if imm < 0:
        if alreadyinverted:
            return None
        return tryInvert()

    def _rotLeftPos(onep, n):
        return [(k+n) % 32 for k in onep]

    def _rotLeftBin(binlist, n):
        return binlist[n:] + binlist[:n]

    immBin = [int(b) for b in "{:032b}".format(imm)]
    onesPos = [31-i for i in range(len(immBin)) if immBin[i] == 1]
    for i in range(31):
        rotatedPos = _rotLeftPos(onesPos, i)
        if max(rotatedPos) < 8:
            # Does it fit in 8 bits?
            # If so, we want to use the put the constant to the far left of the unsigned field
            # (that is, we want as many rotations as possible)
            # Remember that we can only do an EVEN number of right rotations
            if not gccMode:
                rotReal = i + (7 - max(rotatedPos))
                if rotReal % 2 == 1:
                    if max(rotatedPos) < 7:
                        rotReal -= 1
                    else:
                        return None
            else:
                rotReal = i - min(rotatedPos)
                if rotReal % 2 == 1:
                    if max(rotatedPos) < 7:
                        rotReal += 1
                    else:
                        return None

            immBinRot = [str(b) for b in _rotLeftBin(immBin, rotReal)]
            val = int("".join(immBinRot), 2) & 0xFF
            rot = rotReal // 2
            break
    else:
        if alreadyinverted:
            return None
        return tryInvert()
    return val, rot, False




def checkMask(data, posOnes, posZeros):
    v = 0
    for p1 in posOnes:
        v |= 1 << p1
    if data & v != v:
        return False
    v = 0
    for p0 in posZeros:
        v |= 1 << p0
    if data & v != 0:
        return False
    return True


