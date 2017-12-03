import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import simulatorOps.utils as utils
from simulatorOps.abstractOp import AbstractOp, ExecutionException

class BranchOp(AbstractOp):

    def __init__(self):
        super().__init__()
        self._type = utils.InstrType.branch

    def decode(self):
        instrInt = self.instrInt
        if not (utils.checkMask(instrInt, (27, 25), (26,)) or utils.checkMask(instrInt, (24, 21, 4) + tuple(range(8, 20)), (27, 26, 25, 23, 22, 20, 7, 6, 5))):
            raise ExecutionException("masque de décodage invalide pour une instruction de type BRANCH", 
                                        internalError=True)

        # Retrieve the condition field
        self._decodeCondition()
        self.imm = (instrInt >> 25) & 1 != 0

        if self.imm:
            # B or BL
            self.imm = True
            self.link = bool(instrInt & (1 << 24))
            self.offsetImm = instrInt & 0xFFFFFF
            if self.offsetImm & 0x800000:   # Negative offset
                self.offsetImm = -2**24 + self.offsetImm
            # Branch offset is *4 (since an ARM instruction covers 4 bytes)
            self.offsetImm <<= 2

        else:
            # BX
            self.link = False
            self.addrReg = instrInt & 0xF

    def explain(self, simulatorContext):
        bank = simulatorContext.regs.mode
        simulatorContext.regs.deactivateBreakpoints()
        
        self._nextInstrAddr = -1
        
        disassembly = "B"
        description = "<ol>\n"
        disCond, descCond = self._explainCondition()
        description += descCond

        if self.link:      
            self._nextInstrAddr = simulatorContext.regs[15] - simulatorContext.pcoffset + 4
            disassembly += "L"
            self._writeregs = utils.registerWithCurrentBank(14, bank) | utils.registerWithCurrentBank(15, bank)
            self._readregs = utils.registerWithCurrentBank(15, bank)
            description += "<li>Copie la valeur de {}-4 (l'adresse de la prochaine instruction) dans {}</li>\n".format(utils.regSuffixWithBank(15, bank), utils.regSuffixWithBank(14, bank))
        
        if self.imm:
            self._nextInstrAddr = simulatorContext.regs[15] + self.offsetImm
            self._writeregs = utils.registerWithCurrentBank(15, bank)
            self._readregs = utils.registerWithCurrentBank(15, bank)
            valAdd = self.offsetImm
            if valAdd < 0:
                description += "<li>Soustrait la valeur {} à {}</li>\n".format(-valAdd, utils.regSuffixWithBank(15, bank))
            else:
                description += "<li>Additionne la valeur {} à {}</li>\n".format(valAdd, utils.regSuffixWithBank(15, bank))
        else:   # BX
            disassembly += "X"
            self._nextInstrAddr = simulatorContext.regs[self.addrReg]
            self._writeregs = utils.registerWithCurrentBank(15, bank)
            self._readregs = utils.registerWithCurrentBank(self.addrReg, bank)
            description += "<li>Copie la valeur de {} dans {}</li>\n".format(utils.regSuffixWithBank(self.addrReg, bank), utils.regSuffixWithBank(15, bank))

        disassembly += disCond
        disassembly += " {}".format(hex(valAdd)) if self.imm else " {}".format(utils.regSuffixWithBank(self.addrReg, bank))

        if not self._checkCondition(simulatorContext.regs):
            self._nextInstrAddr = simulatorContext.regs[15] + 4 - simulatorContext.pcoffset

        description += "</ol>"
        simulatorContext.regs.reactivateBreakpoints()
        return disassembly, description
    
    def execute(self, simulatorContext):
        if not self._checkCondition(simulatorContext.regs):
            # Nothing to do, instruction not executed
            return

        if self.link:
            simulatorContext.regs[14] = simulatorContext.regs[15] - simulatorContext.pcoffset + 4
            simulatorContext.stepCondition += 1         # We are entering a function, we log it (useful for stepForward and stepOut)
            simulatorContext.callStack.append(simulatorContext.regs[15] - simulatorContext.pcoffset)
        if self.imm:
            simulatorContext.regs[15] = simulatorContext.regs[15] + self.offsetImm
        else:   # BX
            simulatorContext.regs[15] = simulatorContext.regs[self.addrReg]
            simulatorContext.stepCondition -= 1         # We are returning from a function, we log it (useful for stepForward and stepOut)
            if len(simulatorContext.callStack) > 0:
                simulatorContext.callStack.pop()
        
        self.pcmodified = True
