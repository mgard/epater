import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import simulatorOps.utils as utils
from simulatorOps.abstractOp import AbstractOp, ExecutionException

class MulOp(AbstractOp):
    saveStateKeys = frozenset(("condition",
                                "rd", "rn", "rs", "rm",
                                "modifyFlags", "accumulate"))

    def __init__(self):
        super().__init__()
        self._type = utils.InstrType.multiply

    def decode(self):
        instrInt = self.instrInt
        if not (utils.checkMask(instrInt, (7, 4), tuple(range(22, 28)) + (5, 6))):
            raise ExecutionException("Le bytecode à cette adresse ne correspond à aucune instruction valide",
                                        internalError=False)

        # Retrieve the condition field
        self._decodeCondition()
        
        self.rd = (instrInt >> 16) & 0xF
        self.rn = (instrInt >> 12) & 0xF
        self.rs = (instrInt >> 8) & 0xF
        self.rm = instrInt & 0xF

        self.modifyFlags = bool(instrInt & (1 << 20))
        self.accumulate = bool(instrInt & (1 << 21))

    def explain(self, simulatorContext):
        self.resetAccessStates()
        bank = simulatorContext.regs.mode
        simulatorContext.regs.deactivateBreakpoints()
        
        disassembly = ""
        description = "<ol>\n"
        disCond, descCond = self._explainCondition()
        description += descCond

        self._readregs |= utils.registerWithCurrentBank(self.rm, bank)
        self._readregs |= utils.registerWithCurrentBank(self.rs, bank)

        if self.accumulate:
            disassembly = "MLA"
            description += "<li>Effectue une multiplication suivie d'une addition (A*B+C) entre :\n"
            description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(utils.regSuffixWithBank(self.rm, bank))
            description += "<li>Le registre {}</li>\n".format(utils.regSuffixWithBank(self.rs, bank))
            description += "<li>Le registre {}</li></ol>\n".format(utils.regSuffixWithBank(self.rn, bank))
            if self.modifyFlags:
                disassembly += "S"
                description += "<li>Met à jour les drapeaux de l'ALU en fonction du résultat de l'opération</li>\n"
            disassembly += disCond + " R{}, R{}, R{}, R{} ".format(self.rd, self.rm, self.rs, self.rn)
            self._readregs |= utils.registerWithCurrentBank(self.rn, bank)
        else:
            disassembly = "MUL"
            description += "<li>Effectue une multiplication (A*B) entre :\n"
            description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(utils.regSuffixWithBank(self.rm, bank))
            description += "<li>Le registre {}</li></ol>\n".format(utils.regSuffixWithBank(self.rs, bank))
            if self.modifyFlags:
                disassembly += "S"
                description += "<li>Met à jour les drapeaux de l'ALU en fonction du résultat de l'opération</li>\n"
            disassembly += disCond + " R{}, R{}, R{} ".format(self.rd, self.rm, self.rs)

        description += "<li>Écrit le résultat dans R{}</li>".format(self.rd)
        self._writeregs |= utils.registerWithCurrentBank(self.rd, bank)

        if self.modifyFlags:
            self._writeflags = {'c', 'z', 'n'}

        description += "</ol>"
        simulatorContext.regs.reactivateBreakpoints()
        return disassembly, description
    
    def execute(self, simulatorContext):
        if not self._checkCondition(simulatorContext.regs):
            # Nothing to do, instruction not executed
            self.countExecConditionFalse += 1
            return
        self.countExec += 1
        
        op1 = simulatorContext.regs[self.rm]
        op2 = simulatorContext.regs[self.rs]
        if self.accumulate:
            # MLA
            res = op1 * op2 + simulatorContext.regs[self.rn]
        else:
            # MUL
            res = op1 * op2

        simulatorContext.regs[self.rd] = res & 0xFFFFFFFF

        # Z and V are set, C is set to "meaningless value" (see ARM spec 4.7.2), V is unaffected
        workingFlags = {}
        workingFlags['Z'] = res == 0
        workingFlags['N'] = res & 0x80000000  # "N flag will be set to the value of bit 31 of the result" (4.5.1)
        workingFlags['C'] = 0       # I suppose "0" can be qualified as a meaningless value...

        if self.modifyFlags:
            simulatorContext.regs.setAllFlags(workingFlags)
