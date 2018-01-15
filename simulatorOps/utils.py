import struct
import math
from collections import defaultdict, namedtuple
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

conditionFlagsMapping =    {'EQ': {'Z'},
                            'NE': {'Z'},
                            'CS': {'C'},
                            'CC': {'C'},
                            'MI': {'N'},
                            'PL': {'N'},
                            'VS': {'V'},
                            'VC': {'V'},
                            'HI': {'C', 'Z'},
                            'LS': {'C', 'Z'},
                            'GE': {'N', 'V'},
                            'LT': {'N', 'V'},
                            'GT': {'N', 'V', 'Z'},
                            'LE': {'N', 'V', 'Z'},
                            'AL': set()}

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

##############################################################################
###                     Formatting helper functions                        ###
##############################################################################

def registerWithCurrentBank(reg, bank):
    prefixBanks = {"User": "", "FIQ": "FIQ_", "IRQ": "IRQ_", "SVC": "SVC_"}
    listAffectedRegs = ["{}r{}".format(prefixBanks[bank], reg)]

    if bank == "User":
        if reg < 13 or reg == 15:
            listAffectedRegs.append("IRQ_r{}".format(reg))
            listAffectedRegs.append("SVC_r{}".format(reg))
        if reg < 8 or reg == 15:
            listAffectedRegs.append("FIQ_r{}".format(reg))
    elif bank == "IRQ":
        if reg < 13 or reg == 15:
            listAffectedRegs.append("r{}".format(reg))
            listAffectedRegs.append("SVC_r{}".format(reg))
        if reg < 8 or reg == 15:
            listAffectedRegs.append("FIQ_r{}".format(reg))
    elif bank == "SVC":
        if reg < 13 or reg == 15:
            listAffectedRegs.append("r{}".format(reg))
            listAffectedRegs.append("IRQ_r{}".format(reg))
        if reg < 8 or reg == 15:
            listAffectedRegs.append("FIQ_r{}".format(reg))
    elif bank == "FIQ":
        if reg < 8 or reg == 15:
            listAffectedRegs.append("r{}".format(reg))
            listAffectedRegs.append("IRQ_r{}".format(reg))
            listAffectedRegs.append("SVC_r{}".format(reg))
    return set(listAffectedRegs)

def regSuffixWithBank(reg, bank):
    regStr = "R{}".format(reg) if reg < 13 else ["SP", "LR", "PC"][reg-13]
    if bank == "FIQ" and 7 < reg < 15:
        return "{}_fiq".format(regStr)
    elif bank == "IRQ" and 12 < reg < 15:
        return "{}_irq".format(regStr)
    elif bank == "SVC" and 12 < reg < 15:
        return "{}_svc".format(regStr)
    return regStr


##############################################################################
####              Shift related functions and data structures              ###
##############################################################################

shiftInfo = namedtuple("shiftInfo", ["type", "immediate", "value"])

shiftMapping = {'LSL': 0,
                'LSR': 1,
                'ASR': 2,
                'ROR': 3,
                'RRX': 3}

shiftMappingR = {0: 'LSL', 1: 'LSR', 2: 'ASR', 3: 'ROR'}

def shiftToDescription(shift, bank):
    if shift.value == 0 and shift.type == "LSL" and shift.immediate:
        # No shift
        return ""

    desc = "("
    if shift.type == "LSL":
        desc += "décalé vers la gauche (mode LSL)"
    elif shift.type == "LSR":
        desc += "décalé vers la droite (mode LSR)"
    elif shift.type == "ASR":
        desc += "décalé vers la droite (mode ASR)"
    elif shift.type == "ROR":
        if shift.type == 0:
            desc += "permuté vers la droite avec retenue (mode RRX)"
        else:
            desc += "permuté vers la droite (mode ROR)"

    if shift.immediate:
        desc += " de {} {}".format(shift.value, "positions" if shift.value > 1 else "position")
    else:
        desc += " du nombre de positions contenu dans {}".format(regSuffixWithBank(shift.value, bank))

    desc += ")"
    return desc

def shiftToInstruction(shift):
    if shift.value == 0 and shift.type == "LSL" and shift.immediate:
        # No shift
        return ""

    str = ", " + shift.type
    if shift.type == "ROR" and shift.value == 0:
        str = ", RRX"
    if shift.immediate:
        str += " #{}".format(shift.value)
    else:
        str += " R{}".format(shift.value)
    return str


def applyShift(val, shift, cflag):
    """
    Apply the shifting operation described by `shift` to `val`.
    The shift value MUST be an immediate (that is, shift.immediate must be true)
    `cflag` should contain the current value of the carry flag (used only for RRX)
    """
    carryOut = 0
    if shift.type == "LSL":
        if shift.value == 0:            # If there is no shift
            return carryOut, val
        carryOut = (val << (32-shift.value)) & 2**31
        val = (val << shift.value) & 0xFFFFFFFF
    elif shift.type == "LSR":
        if shift.value == 0:
            # Special case : "The form of the shift field which might be expected to correspond to LSR #0 is used to
            # encode LSR #32, which has a zero result with bit 31 of Rm as the carry output."
            val = 0
            carryOut = (val >> 31) & 1
        else:
            carryOut = (val >> (shift.value-1)) & 1
            val = (val >> shift.value) & 0xFFFFFFFF
    elif shift.type == "ASR":
        if shift.value == 0:
            # Special case : "The form of the shift field which might be expected to give ASR #0 is used to encode
            # ASR #32. Bit 31 of Rm is again used as the carry output, and each bit of operand 2 is
            # also equal to bit 31 of Rm. The result is therefore all ones or all zeros, according to the
            # value of bit 31 of Rm."
            carryOut = (val >> 31) & 1
            val = 0 if carryOut == 0 else 0xFFFFFFFF
        else:
            carryOut = (val >> (shift.value-1)) & 1
            firstBit = (val >> 31) & 1
            val = (val >> shift.value) | ((val >> 31) * ((2**shift.value-1) << (32-shift.value)))
    elif shift.type == "ROR":
        if shift.value == 0:
            # The form of the shift field which might be expected to give ROR #0 is used to encode
            # a special function of the barrel shifter, rotate right extended (RRX).
            carryOut = val & 1
            val = (val >> 1) | (int(cflag) << 31)
        else:
            carryOut = (val >> (shift.value-1)) & 1
            val = ((val & (2**32-1)) >> shift.value%32) | (val << (32-(shift.value%32)) & (2**32-1))
    return carryOut, val


##############################################################################
###                          Operation helpers                             ###
##############################################################################

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
