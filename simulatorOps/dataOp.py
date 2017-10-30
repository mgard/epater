import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import utils
from abstractOp import AbstractOp

class DataOp(AbstractOp):
    flagsAndOpMapping = {'MOV': ('Z', 'N'), 
                         'MVN': ('Z', 'N'),
                         'ADD': ('Z', 'N', 'C', 'V'),
                         'ADC': ('Z', 'N', 'C', 'V'),
                         }

    def __init__(self, bytecode):
        super().__init__(bytecode)
        self._type = utils.InstrType.dataop

    def decode(self):
        assert utils.checkMask(self.instrInt, (), (27, 26)),
        instrInt = self.instrInt

        # Retrieve condition filed
        if instrInt >> 28 == 15:    # Invalid condition code
            self.decodeError = True
            return
        self.condition = utils.conditionMappingR[instrInt >> 28]

        # Get the opcode
        self.opcodeNum = (instrInt >> 21) & 0xF
        self.opcode = utils.dataOpcodeMappingR[self.opcodeNum]

        # "Immediate" and "set flags"
        self.imm = bool(instrInt & (1 << 25))
        self.modifyFlags = bool(instrInt & (1 << 20))

        self.rd = (instrInt >> 12) & 0xF    # Destination register
        self.rn = (instrInt >> 16) & 0xF    # First operand register

        if self.imm:
            self.val = instrInt & 0xFF
            # see 4.5.3 of ARM doc to understand the * 2
            self.shift = ("ROR", "imm", ((instrInt >> 8) & 0xF) * 2)       
        else:
            self.val = instrInt & 0xF
            if instrInt & (1 << 4):
                self.shift = (utils.shiftMappingR[(instrInt >> 5) & 0x3], 
                                "reg", 
                                (instrInt >> 8) & 0xF)
            else:
                self.shift = (utils.shiftMappingR[(instrInt >> 5) & 0x3],
                                "imm", 
                                (instrInt >> 7) & 0x1F)

    def explain(self):
        pass
    
    def execute(self):
        pass

    @property
    def affectedRegs(self):
        return () if 7 < self.opcodeNum < 12 else (self.rd,)

    @property
    def affectedFlags(self):
        return () if not self.modifyFlags else self.flagsAndOpMapping[self.opcode]