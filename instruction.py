import struct
import math
from collections import defaultdict
from enum import Enum

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

shiftMapping = {'LSL': 0,
                'LSR': 1,
                'ASR': 2,
                'ROR': 3}

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

def immediateToBytecode(imm):
    scale = math.log2(imm)
    immval, immrot = None, None
    for s in range(8, 30, 2):
        if scale < s:
            div = 2**(s-8)
            if imm % div == 0:
                immval, immrot = imm // div, s-8
            else:
                break
    assert not immval is None
    return immval, immrot

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


def DataInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value
    b = dataOpcodeMapping[mnemonic] << 21

    condSeen = False
    countReg = 0
    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'SETFLAGS':
            b |= 1 << 20
        elif tok.type == 'COND':
            condSeen = True
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
            immval, immrot = immediateToBytecode(tok.value)
            b |= immval
            b |= immrot << 8
        elif tok.type == 'SHIFTREG':
            b |= 1 << 4
            b |= shiftMapping[tok.value[0]] << 5
            b |= tok.value[1] << 8
        elif tok.type == 'SHIFTIMM':
            b |= shiftMapping[tok.value[0]] << 5
            b |= tok.value[1] << 7
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 31

    checkTokensCount(dictSeen)
    return struct.pack("=I", b)


def MemInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value

    b = 1 << 26
    b |= (1 << 20 if mnemonic == "LDR" else 0)
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
                b |= 1 << 25
                b |= tok.value.offset
            elif tok.value.offsettype == "reg":
                b |= tok.value.offset
                b |= shiftMapping[tok.value.shift.type] << 5
                b |= tok.value.shift.count << 7
        elif tok.type == 'MEMACCESSPOST':
            b |= tok.value.base << 16
            if tok.value.direction > 0:
                b |= 1 << 23
            if tok.value.offsettype == "imm":
                b |= 1 << 25
                b |= tok.value.offset
            elif tok.value.offsettype == "reg":
                b |= tok.value.offset
        elif tok.type == 'SHIFTIMM':
            # Should be post increment
            b |= shiftMapping[tok.value.type] << 5
            b |= tok.value.count << 7
        elif tok.type == 'WRITEBACK':
            b |= 1 << 21
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 31

    checkTokensCount(dictSeen)
    return struct.pack("=I", b)


def MultipleMemInstructionToBytecode(asmtokens):
    mnemonic = asmtokens[0].value
    b = 0b100 << 25

    b |= (1 << 20 if mnemonic == "LDM" else 0)
    dictSeen = defaultdict(int)
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            b |= conditionMapping[tok.value] << 28
        elif tok.type == 'WRITEBACK':
            b |= 1 << 21
        elif tok.type == 'REGISTER':
            if dictSeen['REGISTER'] == 0:
                b |= tok.value << 16
            elif dictSeen['REGISTER'] == 1:
                assert dictSeen['LISTREGS'] == 0
                b |= 1 << tok.value     # Not the real encoding when only one reg is present. Is this an actual issue?
        elif tok.type == 'LISTREGS':
            for i in range(tok.value):
                b |= tok.value[i] << i
        elif tok.type == 'UPDATEMODE':
            if mnemonic in ('LDM', 'POP'):
                b |= updateModeLDMMapping[tok.value] << 23
            elif mnemonic in ('STM', 'PUSH'):
                b |= updateModeSTMMapping[tok.value] << 23
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b |= conditionMapping['AL'] << 31

    checkTokensCount(dictSeen)
    return struct.pack("=I", b)

def BranchInstructionToBytecode(self, asmtokens):
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
        elif tok.type == 'CONSTANT':
            b |= tok.value
        dictSeen[tok.type] += 1

    if dictSeen['COND'] == 0:
        b += conditionMapping['AL'] << 31

    checkTokensCount(dictSeen)
    return struct.pack("=I", b)


def DeclareInstructionToBytecode(asmtokens):
    assert asmtokens[0].type == 'DECLARATION'
    info = asmtokens[0].value

    formatletter = "=B" if info.nbits == 8 else "=H" if info.nbits == 16 else "=I" # 32
    return struct.pack(formatletter*info.dim,
                        [0]*info.dim if len(info.vals) > 0 else [int(v, 0) for v in info.vals])


instrToCategoryMapping  = {k:DataInstructionToBytecode for k in dataOpcodeMapping}
instrToCategoryMapping += {k:BranchInstructionToBytecode for k in ['B', 'BL', 'BX']}
instrToCategoryMapping += {k:MemInstructionToBytecode for k in ['LDR', 'STR']}
instrToCategoryMapping += {k:MultipleMemInstructionToBytecode for k in ['LDM', 'STM', 'POP', 'PUSH']}
instrToCategoryMapping += {k:DeclareInstructionToBytecode for k in ['DC', 'DS']}
def InstructionToBytecode(asmtokens):
    assert asmtokens[0].type == 'INSTR'
    return instrToCategoryMapping[asmtokens[0].value](asmtokens)



class InstrType(Enum):
    undefined = -1
    dataop = 0
    memop = 1
    multiplememop = 2
    branch = 3

globalInstrInfo = {'MOV': InstrType.dataop,
                   'ADD': InstrType.dataop,
                   'LDR': InstrType.memop,
                   'STR': InstrType.memop,
                   'LDM': InstrType.multiplememop,
                   'STM': InstrType.multiplememop,
                   'B'  : InstrType.branch,
                   'BX' : InstrType.branch,
                   'BL' : InstrType.branch,
                   }



class InstructionBytecode:
    def __init__(self):
        pass