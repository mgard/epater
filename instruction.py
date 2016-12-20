import struct
import math
from collections import defaultdict
from functools import lru_cache
from enum import Enum

from settings import getSetting

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
    declareOp = 100

    @staticmethod
    def getEncodeFunction(inType):
        return {InstrType.dataop: DataInstructionToBytecode,
                InstrType.memop: MemInstructionToBytecode,
                InstrType.multiplememop: MultipleMemInstructionToBytecode,
                InstrType.branch: BranchInstructionToBytecode,
                InstrType.multiply: MultiplyInstructionToBytecode,
                InstrType.swap: SwapInstructionToBytecode,
                InstrType.softinterrupt: SoftinterruptInstructionToBytecode,
                InstrType.psrtransfer: PSRTransferInstructionToBytecode,
                InstrType.declareOp: DeclareInstructionToBytecode,
                InstrType.shiftop: ShiftInstructionToBytecode,
                InstrType.nopop: NopInstructionToBytecode}[inType]

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

shiftMappingR = {v: k for k,v in shiftMapping.items()}

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

dataOpcodeMappingR = {v: k for k,v in dataOpcodeMapping.items()}

def immediateToBytecode(imm, mode=None, alreadyinverted=False):
    """
    The immediate operand rotate field is a 4 bit unsigned integer which specifies a shift
    operation on the 8 bit immediate value. This value is zero extended to 32 bits, and then
    subject to a rotate right by twice the value in the rotate field. (ARM datasheet, 4.5.3)
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
            rotReal = i + (7 - max(rotatedPos))
            if rotReal % 2 == 1:
                if max(rotatedPos) < 7:
                    rotReal -= 1
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


# TEST CODE
def _immShiftTestCases():
    # Asserted with IAR
    tcases = [(0, 0x000),
              (1, 0x001),
              (255, 0x0ff),
              (256, 0xf40),
              (260, 0xf41),
              (1024, 0xe40),
              (4096, 0xd40),
              (8192, 0xd80),
              (65536, 0xb40),
              (0x80000000, 0x480)]
    negtcases = [(-1, 0x000),
                 (-2, 0x001),
                 (-255, 0x0fe)]

    for case in tcases:
        print("Testing case {}... ".format(case[0]), end="")
        val, rot, inv = immediateToBytecode(case[0])
        assert 0 <= val <= 255, "Echec cas {} (pas entre 0 et 255) : {}".format(case[0], val)
        cmpval = val & 0xFF | ((rot & 0xF) << 8)
        assert case[1] == cmpval, "Echec cas {} (invalide) : {} vs {}".format(case[0], hex(cmpval), hex(case[1]))
        print("OK")
    for case in negtcases:
        print("Testing case {}... ".format(case[0]), end="")
        val, rot, inv = immediateToBytecode(case[0])
        assert 0 <= val <= 255, "Echec cas {} (pas entre 0 et 255) : {}".format(case[0], val)
        cmpval = val & 0xFF | ((rot & 0xF) << 8)
        assert case[1] == cmpval, "Echec cas {} (invalide) : {} vs {}".format(case[0], hex(cmpval), hex(case[1]))
        print("OK")
# END TEST CODE


def checkTokensCount(tokensDict):
    # Not a comprehensive check
    assert tokensDict['COND'] <= 1
    assert tokensDict['SETFLAGS'] <= 1
    assert tokensDict['SHIFTREG'] + tokensDict['SHIFTIMM'] <= 1
    assert tokensDict['CONSTANT'] <= 1
    assert tokensDict['BYTEONLY'] <= 1
    assert tokensDict['MEMACCESSPRE'] + tokensDict['MEMACCESSPOST'] <= 1
    assert tokensDict['WRITEBACK'] <= 1
    assert tokensDict['UPDATEMODE'] <= 1

def NopInstructionToBytecode(asmtokens):
    b = 0x320F000
    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 28
    return struct.pack("<I", b)


def ShiftInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value

    b = dataOpcodeMapping['MOV'] << 21      # Always MOV
    dictSeen = defaultdict(int)

    mnemonic = "ROR" if mnemonic == 'RRX' else mnemonic
    b |= shiftMapping[mnemonic] << 5

    for tok in asmtokens[1:]:
        if tok.type == 'SETFLAGS':
            b |= 1 << 20
        elif tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'REGISTER':
            if dictSeen['REGISTER'] == 0:
                b |= tok.value << 12
            elif dictSeen['REGISTER'] == 1:
                b |= tok.value
            else:
                # Shift by register
                b |= 1 << 4
                b |= tok.value << 8
        elif tok.type == 'CONSTANT':
            # Shift by a constant
            if mnemonic in ('LSR', 'ASR') and tok.value == 32:
                # Special case, see ARM datasheet, 4.5.2
                pass        # Nothing to do, we actually want to encode "0"
            else:
                b |= tok.value << 7
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 28

    checkTokensCount(dictSeen)
    return struct.pack("<I", b)


def DataInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value

    b = dataOpcodeMapping[mnemonic] << 21

    dictSeen = defaultdict(int)
    if mnemonic in ('TEQ', 'TST', 'CMP', 'CMN'):
        # No destination register for these instructions
        dictSeen['REGISTER'] = 1

        # "TEQ, TST, CMP and CMN do not write the result of their operation but do set
        # flags in the CPSR. An assembler should always set the S flag for these instructions
        # even if this is not specified in the mnemonic" (4-15, ARM7TDMI-S Data Sheet)
        b |= 1 << 20

    for tok in asmtokens[1:]:
        if tok.type == 'SETFLAGS':
            b |= 1 << 20
        elif tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'REGISTER':
            if dictSeen['REGISTER'] == 0:
                b |= tok.value << 12
            elif dictSeen['REGISTER'] == 2 or mnemonic in ('MOV', 'MVN'):
                b |= tok.value
            else:
                b |= tok.value << 16
        elif tok.type == 'CONSTANT':
            b |= 1 << 25
            typeInverse = None
            if mnemonic in ('MOV', 'MVN', 'AND', 'BIC'):
                typeInverse = 'logical'
            elif mnemonic in ('ADD', 'SUB', 'CMP', 'CMN'):
                typeInverse = 'arithmetic'
            ret = immediateToBytecode(tok.value, typeInverse)
            if ret is None:
                # Error : cannot generate the constant!
                assert False
            immval, immrot, inverse = ret
            if typeInverse is not None and inverse:
                # We can fit the constant, but we have to swap instructions in order to do so
                if mnemonic == 'MOV':
                    # We replace the MOV opcode by a MVN
                    b |= dataOpcodeMapping['MVN'] << 21     # MVN is 1111 opcode
                elif mnemonic == 'MVN':
                    # We replace the MVN opcode by a MOV
                    b ^= 1 << 22
                elif mnemonic == 'ADD':
                    # We replace the ADD opcode by a SUB
                    b &= (~(0xF << 21)) & 0xFFFFFFFF
                    b |= dataOpcodeMapping['SUB'] << 21
                elif mnemonic == 'SUB':
                    # We replace the SUB opcode by an ADD
                    b &= (~(0xF << 21)) & 0xFFFFFFFF
                    b |= dataOpcodeMapping['ADD'] << 21
                elif mnemonic == 'CMP':
                    # We replace CMP by CMN
                    b |= 1 << 21
                elif mnemonic == 'CMN':
                    # We replace CMN by CMP
                    b &= (~(0x1 << 21)) & 0xFFFFFFFF
                elif mnemonic == 'AND':
                    # We replace AND with BIC
                    # AND is 0000 so we don't have to "erase" it
                    b |= dataOpcodeMapping['BIC'] << 21
                elif mnemonic == 'BIC':
                    # We replace BIC with AND
                    # AND is 0000 so we just have to set the opcode bits to 0
                    b &= (~(0xF << 21)) & 0xFFFFFFFF
            b |= immval
            b |= immrot << 8
        elif tok.type == 'SHIFTREG':
            b |= 1 << 4
            b |= shiftMapping[tok.value[0]] << 5
            b |= tok.value[1] << 8
        elif tok.type == 'SHIFTIMM':
            b |= shiftMapping[tok.value[0]] << 5
            if tok.value[0] in ('LSR', 'ASR') and tok.value[1] == 32:
                # Special case, see ARM datasheet, 4.5.2
                pass        # Nothing to do, we actually want to encode "0"
            elif tok.value[0] == 'RRX':
                pass        # Nothing to do, we actually want to encode "0" with ROR mode
            else:
                b |= tok.value[1] << 7
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 28

    checkTokensCount(dictSeen)
    return struct.pack("<I", b)


def MemInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value

    b = 1 << 26
    b |= (1 << 20 if mnemonic == "LDR" else 0)
    setWB0 = False
    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'BYTEONLY':
            b |= 1 << 22
        elif tok.type == 'REGISTER':
            b |= tok.value << 12
        elif tok.type == 'MEMACCESSPRE':
            b |= 1 << 24
            b |= tok.value.base << 16
            if tok.value.direction > 0:
                b |= 1 << 23
            if tok.value.offsettype == "imm":
                b |= tok.value.offset
            elif tok.value.offsettype == "reg":
                b |= 1 << 25
                b |= tok.value.offset
                b |= shiftMapping[tok.value.shift.type] << 5
                b |= tok.value.shift.count << 7
        elif tok.type == 'MEMACCESSPOST':
            b |= tok.value.base << 16
            if tok.value.direction > 0:
                b |= 1 << 23
            if tok.value.offsettype == "imm":
                b |= tok.value.offset
            elif tok.value.offsettype == "reg":
                b |= 1 << 25
                b |= tok.value.offset
            setWB0 = True
        elif tok.type == 'SHIFTIMM':
            # Should be post increment
            b |= shiftMapping[tok.value.type] << 5
            b |= tok.value.count << 7
        elif tok.type == 'WRITEBACK':
            b |= 1 << 21
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 28

    if setWB0:
        # "In the case of post-indexed addressing, the write back bit is redundant and must be set to zero,
        #  since the old base value can be retained by setting the offset to zero. Therefore post-indexed
        #  data transfers always write back the modified base" (4.9.1)
        b &= (~(1 << 21)) & 0xFFFFFFFF

    checkTokensCount(dictSeen)
    return struct.pack("<I", b)


def MultipleMemInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value
    b = 0b100 << 25

    b |= (1 << 20 if mnemonic in ('LDM', 'POP') else 0)
    if mnemonic in ('PUSH', 'POP'):
        # SP is always used as base register with PUSH and POP
        b |= 13 << 16
        # Write-back
        b |= 1 << 21
    if mnemonic == 'POP':       # POP regs is equivalent to LDM SP!, regs
        # Set mode to UP (add offset)
        b |= 1 << 23
    if mnemonic == 'PUSH':      # PUSH regs is equivalent to STM SP!, regs
        # Pre-increment
        b |= 1 << 24

    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'WRITEBACK':
            b |= 1 << 21
        elif tok.type == 'REGISTER':
            if dictSeen['REGISTER'] == 0 and mnemonic not in ('PUSH', 'POP'):
                b |= tok.value << 16
            elif dictSeen['REGISTER'] == 1:
                assert dictSeen['LISTREGS'] == 0
                b |= 1 << tok.value     # Not the real encoding when only one reg is present. Is this an actual issue?
        elif tok.type == 'LISTREGS':
            listreg, sbit = tok.value
            for i in range(len(listreg)):
                b |= listreg[i] << i
            if sbit:
                b |= 1 << 22
        elif tok.type == 'UPDATEMODE':
            if mnemonic == 'LDM':
                b |= updateModeLDMMapping[tok.value] << 23
            elif mnemonic == 'STM':
                b |= updateModeSTMMapping[tok.value] << 23
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 28

    if dictSeen['UPDATEMODE'] == 0:
        if mnemonic == 'LDM':
            b |= updateModeLDMMapping["IA"] << 23
        elif mnemonic == 'STM':
            b |= updateModeLDMMapping["IA"] << 23

    checkTokensCount(dictSeen)
    return struct.pack("<I", b)

def BranchInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value

    if mnemonic == 'BX':
        b = 0b000100101111111111110001 << 4
    else:
        b = 5 << 25
        if mnemonic == 'BL':
            b |= 1 << 24

    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'REGISTER':
            # Only for BX
            b |= tok.value
        elif tok.type == 'MEMACCESSPRE':
            # When we find a label in the previous parsing stage,
            # we replace it with a MEMACCESSPRE token, even if this
            # token cannot appear in actual code
            val = tok.value.offset >> 2 if tok.value.direction >= 0 else (((~tok.value.offset)+1) >> 2) & 0xFFFFFF
            b |= val
        elif tok.type == 'CONSTANT':
            b |= tok.value >> 2
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b += conditionMapping['AL'] << 28

    checkTokensCount(dictSeen)
    return struct.pack("<I", b)


def MultiplyInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value

    b = 9 << 4
    if mnemonic == 'MLA':
        b |= 1 << 21

    countReg = 0
    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'SETFLAGS':
            b |= 1 << 20
        elif tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'REGISTER':
            if dictSeen['REGISTER'] == 0:
                b |= tok.value << 16
            elif dictSeen['REGISTER'] == 1:
                b |= tok.value
            elif dictSeen['REGISTER'] == 2:
                b |= tok.value << 8
            else:
                b |= tok.value << 12
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 28

    checkTokensCount(dictSeen)
    return struct.pack("<I", b)


def SwapInstructionToBytecode(asmtokens):
    # Todo
    raise NotImplementedError()


def PSRTransferInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value
    b = 1 << 24
    if mnemonic == 'MRS':
        # Read the PSR
        b |= 0xF << 16
    else:
        # Write the PSR
        b |= 0x28F << 12

    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'REGISTER':
            if mnemonic == 'MRS':   # Destination register
                b |= tok.value << 12
            else:                   # Source register
                b |= tok.value
        elif tok.type == 'CONTROLREG':
            # Which PSR to read/write
            if tok.value[0] == 'SPSR':
                b |= 1 << 22
            if tok.value[1] == 'all' and mnemonic == 'MSR':
                b |= 1 << 16
        elif tok.type == 'CONSTANT':
            b |= 1 << 25
            # TODO : add shift
            b |= tok.value
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b += conditionMapping['AL'] << 28

    checkTokensCount(dictSeen)
    return struct.pack("<I", b)


def SoftinterruptInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value
    b = 0xF << 24
    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'SWICONSTANT' or tok.type == 'CONSTANT':
            b |= tok.value & 0xFFFFFF       # Only 24 bits
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 28

    checkTokensCount(dictSeen)
    return struct.pack("<I", b)


def DeclareInstructionToBytecode(asmtokens):
    assert asmtokens[0].type == 'DECLARATION', str((asmtokens[0].type, asmtokens[0].value))
    info = asmtokens[0].value
    formatletter = "B" if info.nbits == 8 else "H" if info.nbits == 16 else "I" # 32
    bitmask = 0xFF if info.nbits == 8 else 0xFFFF if info.nbits == 16 else 0xFFFFFFFF # 32
    if len(info.vals) == 0:
        dimBytes = info.dim * info.nbits // 8
        return struct.pack("<"+"B"*dimBytes, *[getSetting("fillValue")]*dimBytes)
    else:
        return struct.pack("<" + formatletter * info.dim, *[v & bitmask for v in info.vals])


def InstructionToBytecode(asmtokens):
    assert asmtokens[0].type in ('INSTR', 'DECLARATION')
    tp = globalInstrInfo[asmtokens[0].value if asmtokens[0].type == 'INSTR' else asmtokens[0].value.type]
    return InstrType.getEncodeFunction(tp)(asmtokens)


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
    condition = conditionMappingR[instrInt >> 28]
    miscInfo = None

    if checkMask(instrInt, (24, 25, 26, 27), ()): # Software interrupt
        category = InstrType.softinterrupt
        miscInfo = instrInt & (0xFF << 24)

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
            if instrInt & (1 << 4):
                shift = (shiftMappingR[(instrInt >> 5) & 0x3], "reg", (instrInt >> 8) & 0xF)
            else:
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
                    'operandadd': rd}

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
        flagsOnly = bool(instrInt & (1 << 16))
        imm = bool(instrInt & (1 << 25))
        rd = (instrInt >> 12) & 0xF

        if imm and flagsOnly:       # Immediate mode is allowed only for flags-only mode
            val = instrInt & 0xFF
            shift = ("ROR", "imm", ((instrInt >> 8) & 0xF) * 2)       # see 4.5.3 of ARM doc to understand the * 2
        else:
            val = instrInt & 0xF
            shift = ("ROR", "imm", 0)       # No rotate with registers for these particular instructions
        op2 = (val, shift)

        miscInfo = {'write': modeWrite,
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
        assert False, "Unknown instruction!"

    return category, affectedRegs, condition, miscInfo

