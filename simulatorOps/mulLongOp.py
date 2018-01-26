import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import simulatorOps.utils as utils
from simulatorOps.abstractOp import AbstractOp, ExecutionException

class MulLongOp(AbstractOp):
    saveStateKeys = frozenset(("condition", 
                                "rdHi", "rdLo", "rs", "rm",
                                "modifyFlags", "accumulate", "signed"))

    def __init__(self):
        super().__init__()
        self._type = utils.InstrType.multiplylong

    def decode(self):
        instrInt = self.instrInt
        if not (utils.checkMask(instrInt, (7, 4, 23), tuple(range(24, 28)) + (5, 6))):
            raise ExecutionException("masque de décodage invalide pour une instruction de type MULLONG", 
                                        internalError=True)

        # Retrieve the condition field
        self._decodeCondition()
        
        self.rdHi = (instrInt >> 16) & 0xF
        self.rdLo = (instrInt >> 12) & 0xF
        self.rs = (instrInt >> 8) & 0xF
        self.rm = instrInt & 0xF

        self.modifyFlags = bool(instrInt & (1 << 20))
        self.accumulate = bool(instrInt & (1 << 21))
        self.signed = bool(instrInt & (1 << 22))

    def explain(self, simulatorContext):
        self.resetAccessStates()
        bank = simulatorContext.regs.mode
        simulatorContext.regs.deactivateBreakpoints()
        
        self._nextInstrAddr = -1
        
        disassembly = ""
        description = "<ol>\n"
        disCond, descCond = self._explainCondition()
        description += descCond

        if self.signed:
            disassembly = "S"
        else:
            disassembly = "U"
        
        self._readregs |= utils.registerWithCurrentBank(self.rm, bank)
        self._readregs |= utils.registerWithCurrentBank(self.rs, bank)

        if self.accumulate:
            # MLAL
            disassembly += "MLAL"
            description += "<li>Effectue une multiplication et une addition {} sur 64 bits (A*B+[C,D]) entre :\n".format("signées" if self.signed else "non signées")
            description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(utils.regSuffixWithBank(self.rm, bank))
            description += "<li>Le registre {}</li>\n".format(utils.regSuffixWithBank(self.rs, bank))
            description += "<li>Le registre {}</li>\n".format(utils.regSuffixWithBank(self.rdHi, bank))
            description += "<li>Le registre {}</li></ol>\n".format(utils.regSuffixWithBank(self.rdLo, bank))
            self._readregs |= utils.registerWithCurrentBank(self.rdLo, bank)
            self._readregs |= utils.registerWithCurrentBank(self.rdHi, bank)
        else:
            # MULL
            disassembly += "MULL"
            description += "<li>Effectue une multiplication {} (A*B) entre :\n".format("signée" if self.signed else "non signée")
            description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(utils.regSuffixWithBank(self.rm, bank))
            description += "<li>Le registre {}</li></ol>\n".format(utils.regSuffixWithBank(self.rs, bank))

        if self.modifyFlags:
            disassembly += "S"
            description += "<li>Met à jour les drapeaux de l'ALU en fonction du résultat de l'opération</li>\n"
        disassembly += " R{}, R{}, R{}, R{} ".format(self.rdLo, self.rdHi, self.rm, self.rs)
        description += "<li>Écrit les 32 MSB du résultat dans R{} et les 32 LSB dans R{}</li>".format(self.rdHi, self.rdLo)
        self._writeregs |= utils.registerWithCurrentBank(self.rdLo, bank)
        self._writeregs |= utils.registerWithCurrentBank(self.rdHi, bank)

        if self.modifyFlags:
            self._writeflags = set(('z', 'c', 'n'))

        description += "</ol>"
        simulatorContext.regs.reactivateBreakpoints()
        return disassembly, description
    
    def execute(self, simulatorContext):
        if not self._checkCondition(simulatorContext.regs):
            # Nothing to do, instruction not executed
            self.countExecConditionFalse += 1
            return
        self.countExec += 1
        workingFlags = {}

        op1 = simulatorContext.regs[self.rm]
        op2 = simulatorContext.regs[self.rs]

        res = (simulatorContext.regs[self.rdHi] << 32) + simulatorContext.regs[self.rdLo]
        if self.signed:
            op1 -= (op1 >> 31 & 1) << 32
            op2 -= (op2 >> 31 & 1) << 32
            res -= (res >> 63 & 1) << 64

        if self.accumulate:
            # MLAL
            res += (op1 * op2)
        else:
            # MULL
            res = op1 * op2

        if self.signed and res < 0:
            res += 1 << 64

        simulatorContext.regs[self.rdHi] = res >> 32 & 0xFFFFFFFF
        simulatorContext.regs[self.rdLo] = res & 0xFFFFFFFF

        # Z and N are set, V and C is set to "meaningless value" (see ARM spec 4.8.2)
        workingFlags['Z'] = res == 0
        workingFlags['N'] = res & (1 << 63)  # "N flag will be set to the value of bit 63 of the result" (4.8.2)
        workingFlags['C'] = 0       # I suppose "0" can be qualified as a meaningless value...
        workingFlags['V'] = 0       # I suppose "0" can be qualified as a meaningless value...

        if self.modifyFlags:
            simulatorContext.regs.setAllFlags(workingFlags)
