import struct
import math
from collections import defaultdict
from functools import lru_cache
from enum import Enum

"""
Tools to decode instructions.
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


def shiftVal(self, val, shiftInfo):
    # TODO : remove self
    shiftamount = self.regs[shiftInfo[2]].get() & 0xF if shiftInfo[1] == 'reg' else shiftInfo[2]
    carryOut = 0
    if shiftInfo[0] == "LSL":
        carryOut = (val << (32-shiftamount)) & 2**31
        val = (val << shiftamount) & 0xFFFFFFFF
    elif shiftInfo[0] == "LSR":
        if shiftamount == 0:
            # Special case : "The form of the shift field which might be expected to correspond to LSR #0 is used to
            # encode LSR #32, which has a zero result with bit 31 of Rm as the carry output."
            val = 0
            carryOut = (val >> 31) & 1
        else:
            carryOut = (val >> (shiftamount-1)) & 1
            val = (val >> shiftamount) & 0xFFFFFFFF
    elif shiftInfo[0] == "ASR":
        if shiftamount == 0:
            # Special case : "The form of the shift field which might be expected to give ASR #0 is used to encode
            # ASR #32. Bit 31 of Rm is again used as the carry output, and each bit of operand 2 is
            # also equal to bit 31 of Rm. The result is therefore all ones or all zeros, according to the
            # value of bit 31 of Rm."
            carryOut = (val >> 31) & 1
            val = 0 if carryOut == 0 else 0xFFFFFFFF
        else:
            carryOut = (val >> (shiftamount-1)) & 1
            firstBit = (val >> 31) & 1
            val = (val >> shiftamount) | ((val >> 31) * ((2**shiftamount-1) << (32-shiftamount)))
    elif shiftInfo[0] == "ROR":
        if shiftamount == 0:
            # The form of the shift field which might be expected to give ROR #0 is used to encode
            # a special function of the barrel shifter, rotate right extended (RRX).
            carryOut = val & 1
            val = (val >> 1) | (int(self.flags['C']) << 31)
        else:
            carryOut = (val >> (shiftamount-1)) & 1
            val = ((val & (2**32-1)) >> shiftamount%32) | (val << (32-(shiftamount%32)) & (2**32-1))
    return carryOut, val


def addWithCarry(op1, op2, carryIn):
    def toSigned(n):
        return n - 2**32 if n & 0x80000000 else n
    # See AddWithCarry() definition, p.40 (A2-8) of ARM Architecture Reference Manual
    op1 &= 0xFFFFFFFF
    op2 &= 0xFFFFFFFF
    usum = op1 + op2 + int(carryIn)
    ssum = toSigned(op1) + toSigned(op2) + int(carryIn)
    r = usum & 0xFFFFFFFF
    carryOut = usum != r
    overflowOut = ssum != toSigned(r)
    return r, carryOut, overflowOut
