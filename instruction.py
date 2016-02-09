import struct
import math

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


shiftMapping = {'LSL': 0,
                'LSR': 1,
                'ASR': 2,
                'ROR': 3}

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


def DataInstructionToBytecode(self, asmtokens):
    assert asmtokens[0].type == 'INSTR'
    mnemonic = asmtokens[0].value
    b = dataOpcodeMapping[mnemonic] << 21

    condSeen = False
    countReg = 0
    for tok in asmtokens[1:]:
        if tok.type == 'SETFLAGS':
            b += 1 << 20
        elif tok.type == 'COND':
            condSeen = True
            b += conditionMapping[tok.value] << 28
        elif tok.type == 'REGISTER':
            if countReg == 0:
                b += tok.value << 12
            elif countReg == 2 or mnemonic in ('MOV', 'MVN'):
                b += tok.value
            else:
                b += tok.value << 16
            countReg += 1
        elif tok.type == 'CONSTANT':
            b += 1 << 25
            immval, immrot = immediateToBytecode(tok.value)
            b += immval
            b += immrot << 8
        elif tok.type == 'SHIFTREG':
            b += 1 << 4
            b += shiftMapping[tok.value[0]] << 5
            b += tok.value[1] << 8
        elif tok.type == 'SHIFTIMM':
            b += shiftMapping[tok.value[0]] << 5
            b += tok.value[1] << 7

    if not condSeen:
        b += conditionMapping['AL'] << 31

    return struct.pack("=I", b)


def MemInstructionToBytecode(self, asmtokens):
    assert asmtokens[0].type == 'INSTR'
    mnemonic = asmtokens[0].value

    b = 1 << 26
    b = (1 if mnemonic == "LDR" else 0) << 20
    condSeen = False
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            condSeen = True
            b += conditionMapping[tok.value] << 28
        elif tok.type == 'BYTEONLY':
            b += 1 << 22
        elif tok.type == 'REGISTER':
            b += tok.value << 12
        elif tok.type == 'MEMACCESSPRE':
            b += 1 << 24
            b += tok.value[0] << 16
            if tok.value[3] > 0:
                b += 1 << 23
            if tok.value[4]:
                b += 1 << 21
            if tok.value[1] == "imm":
                b += 1 << 25
                b += tok.value[2]
            elif tok.value[1] == "reg":
                b += tok.value[2]
                b += shiftMapping[tok.value[5][0]] << 5
                b += tok.value[5][1] << 7
        elif tok.type == 'MEMACCESSPOST':
            b += tok.value[0] << 16
            if tok.value[3] > 0:
                b += 1 << 23
            if tok.value[1] == "imm":
                b += 1 << 25
                b += tok.value[2]
            elif tok.value[1] == "reg":
                b += tok.value[2]
        elif tok.type == 'SHIFTIMM':
            # Should be post increment
            b += shiftMapping[tok.value[0]] << 5
            b += tok.value[1] << 7

    if not condSeen:
        b += conditionMapping['AL'] << 31
    return struct.pack("=I", b)


def BranchInstructionToBytecode(self, asmtokens):
    assert asmtokens[0].type == 'INSTR'
    mnemonic = asmtokens[0].value

    if mnemonic == 'BX':
        b = 0b000100101111111111110001 << 4
    else:
        b = 5 << 25
        if mnemonic == 'BL':
            b += 1 << 24

    condSeen = False
    for tok in asmtokens[1:]:
        if tok.type == 'COND':
            condSeen = True
            b += conditionMapping[tok.value] << 28
        elif tok.type == 'REGISTER':
            # Only for BX
            b += tok.value
        elif tok.type == 'CONSTANT':
            b += tok.value

    if not condSeen:
        b += conditionMapping['AL'] << 31
    return struct.pack("=I", b)


def DeclareInstructionToBytecode(self, asmtokens):
    assert asmtokens[0].type == 'DECLARATION'

    formatletter = "=B" if asmtokens[0].value[0] == 8 else "=H" if asmtokens[0].value[0] == 16 else "=I"
    return struct.pack(formatletter*len(asmtokens[0].value[1]),
                        [int(v, 0) for v in asmtokens[0].value[1]])


class InstructionBytecode:
    def __init__(self):
        pass