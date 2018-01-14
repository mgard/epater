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


@lru_cache(maxsize=256)
def BytecodeToInstrInfos(bc):
    """
    :param bc: The current instruction, in a bytes object
    :return: A tuple containing four elements. The first is a *InstrType* value
    that corresponds to the type of the current instruction. The second is a
    tuple containing the registers indices that see their value modified by
    this instruction. The third is a decoding of the condition code.
    Finally, the fourth element is not globally defined, and is used by
    the decoder to put informations relevant to the current instruction. For
    instance, when decoding a data processing instruction, this fourth element
    will, amongst other things, contain the opcode of the request operation.
    """
    assert len(bc) == 4 # 32 bits
    instrInt = struct.unpack("<I", bc)[0]      # It's easier to work with integer objects when it comes to bit manipulation

    affectedRegs = ()
    if instrInt >> 28 == 15:
        return InstrType.undefined, affectedRegs, None, {}

    condition = conditionMappingR[instrInt >> 28]
    miscInfo = None

    if checkMask(instrInt, (24, 25, 26, 27), ()): # Software interrupt
        category = InstrType.softinterrupt
        miscInfo = instrInt & 0xFFFFFF

    elif checkMask(instrInt, (4, 25, 26), (27,)):    # Undefined instruction
        category = InstrType.undefined

    elif checkMask(instrInt, (27, 25), (26,)):       # Branch
        category = InstrType.branch
        setlr = bool(instrInt & (1 << 24))
        if setlr:
            affectedRegs = (14,)
        offset = instrInt & 0xFFFFFF
        if offset & 0x800000:   # Negative offset
            offset = -2**24 + offset
        miscInfo = {'mode': 'imm',
                    'L': setlr,
                    'offset': offset << 2}

    elif checkMask(instrInt, (27,), (26, 25)):       # Block data transfer
        category = InstrType.multiplememop
        pre = bool(instrInt & (1 << 24))
        sign = 1 if instrInt & (1 << 23) else -1
        sbit = bool(instrInt & (1 << 22))
        writeback = bool(instrInt & (1 << 21))
        mode = "LDR" if instrInt & (1 << 20) else "STR"

        basereg = (instrInt >> 16) & 0xF
        reglist = instrInt & 0xFFFF
        affectedRegs = []
        for i in range(16):
            if reglist & (1 << i):
                affectedRegs.append(i)
        affectedRegs = tuple(affectedRegs)

        miscInfo = {'base': basereg,
                    'reglist': reglist,
                    'pre': pre,
                    'sign': sign,
                    'writeback': writeback,
                    'mode': mode,
                    'sbit': sbit}

    elif checkMask(instrInt, (26, 25), (4, 27)) or checkMask(instrInt, (26,), (25, 27)):    # Single data transfer
        category = InstrType.memop

        imm = not bool(instrInt & (1 << 25))   # For LDR/STR, imm is 0 if offset IS an immediate value (4-26 datasheet)
        pre = bool(instrInt & (1 << 24))
        sign = 1 if instrInt & (1 << 23) else -1
        byte = bool(instrInt & (1 << 22))
        writeback = bool(instrInt & (1 << 21)) or not pre       # See 4.9.1 (with post, writeback is redundant and always on)
        mode = "LDR" if instrInt & (1 << 20) else "STR"

        basereg = (instrInt >> 16) & 0xF
        destreg = (instrInt >> 12) & 0xF
        if imm:
            offset = instrInt & 0xFFF
        else:
            rm = instrInt & 0xF
            # Not register shift
            shift = (shiftMappingR[(instrInt >> 5) & 0x3] , "imm", (instrInt >> 7) & 0x1F)
            offset = (rm, shift)

        affectedRegs = (destreg,) if not writeback else (destreg, basereg)
        miscInfo = {'base': basereg,
                    'rd': destreg,
                    'offset': offset,
                    'imm': imm,
                    'pre': pre,
                    'sign': sign,
                    'byte': byte,
                    'writeback': writeback,
                    'mode': mode}

    elif checkMask(instrInt, (24, 21, 4) + tuple(range(8, 20)), (27, 26, 25, 23, 22, 20, 7, 6, 5)): # BX
        category = InstrType.branch
        miscInfo = {'mode': 'reg',
                    'L': False,
                    'offset': instrInt & 0xF}

    elif checkMask(instrInt, (7, 4), tuple(range(22, 28)) + (5, 6)):    # MUL or MLA
        category = InstrType.multiply
        rd = (instrInt >> 16) & 0xF
        rn = (instrInt >> 12) & 0xF
        rs = (instrInt >> 8) & 0xF
        rm = instrInt & 0xF
        affectedRegs = (rd,)

        flags = bool(instrInt & (1 << 20))
        accumulate = bool(instrInt & (1 << 21))

        miscInfo = {'accumulate':accumulate,
                    'setflags': flags,
                    'rd': rd,
                    'operandsmul': (rm, rs),
                    'operandadd': rn}

    elif checkMask(instrInt, (7, 4, 23), tuple(range(24, 28)) + (5, 6)):    # UMULL, SMULL, UMLAL or SMLAL
        category = InstrType.multiplylong
        rdHi = (instrInt >> 16) & 0xF
        rdLo = (instrInt >> 12) & 0xF
        rs = (instrInt >> 8) & 0xF
        rm = instrInt & 0xF
        affectedRegs = (rdHi,rdLo,)

        flags = bool(instrInt & (1 << 20))
        accumulate = bool(instrInt & (1 << 21))
        signed = bool(instrInt & (1 << 22))

        miscInfo = {'accumulate':accumulate,
                    'setflags': flags,
                    'signed': signed,
                    'rdHi': rdHi,
                    'rdLo': rdLo,
                    'operandsmul': (rm, rs),
                    'operandadd': (rdHi, rdLo)}

    elif checkMask(instrInt, (7, 4, 24), (27, 26, 25, 23, 21, 20, 11, 10, 9, 8, 6, 5)): # Swap
        category = InstrType.swap
        # TODO

    elif checkMask(instrInt, (25, 24, 21), (27, 26, 23, 22, 20, 19, 18, 17, 16)):       # NOP
        category = InstrType.nopop

    elif checkMask(instrInt, (19, 24), (27, 26, 23, 20)):       # MRS or MSR
        # This one is tricky
        # The signature looks like a data processing operation, BUT
        # it sets the "opcode" to an operation beginning with 10**, and the only operations that match this are TST, TEQ, CMP and CMN
        # It is said that for these ops, the S flag MUST be set to 1
        # With MSR and MRS, the bit representing the S flag is always 0, so we can differentiate these instructions...
        category = InstrType.psrtransfer

        usespsr = bool(instrInt & (1 << 22))
        modeWrite = bool(instrInt & (1 << 21))
        flagsOnly = not bool(instrInt & (1 << 16))
        imm = bool(instrInt & (1 << 25))
        rd = (instrInt >> 12) & 0xF

        if imm and flagsOnly:       # Immediate mode is allowed only for flags-only mode
            val = instrInt & 0xFF
            shift = ("ROR", "imm", ((instrInt >> 8) & 0xF) * 2)       # see 4.5.3 of ARM doc to understand the * 2
        else:
            val = instrInt & 0xF
            shift = ("ROR", "imm", 0)       # No rotate with registers for these particular instructions
        op2 = (val, shift)

        miscInfo = {'opcode': "MSR" if modeWrite else "MRS",
                    'write': modeWrite,
                    'usespsr': usespsr,
                    'flagsOnly': flagsOnly,
                    'imm': imm,
                    'op2': op2,
                    'rd': rd}       # Only valid if modeWrite == False

    elif checkMask(instrInt, (), (27, 26)):     # Data processing
        category = InstrType.dataop
        opcodeNum = (instrInt >> 21) & 0xF
        opcode = dataOpcodeMappingR[opcodeNum]

        imm = bool(instrInt & (1 << 25))
        flags = bool(instrInt & (1 << 20))

        rd = (instrInt >> 12) & 0xF
        rn = (instrInt >> 16) & 0xF

        if imm:
            val = instrInt & 0xFF
            shift = ("ROR", "imm", ((instrInt >> 8) & 0xF) * 2)       # see 4.5.3 of ARM doc to understand the * 2
        else:
            val = instrInt & 0xF
            if instrInt & (1 << 4):
                shift = (shiftMappingR[(instrInt >> 5) & 0x3], "reg", (instrInt >> 8) & 0xF)
            else:
                shift = (shiftMappingR[(instrInt >> 5) & 0x3] , "imm", (instrInt >> 7) & 0x1F)
        op2 = (val, shift)

        if not 7 < opcodeNum < 12:
            affectedRegs = (rd,)

        miscInfo = {'opcode': opcode,
                'rd': rd,
                'setflags': flags,
                'imm': imm,
                'rn': rn,
                'op2': op2}

    else:
        category = InstrType.undefined

    return category, affectedRegs, condition, miscInfo

