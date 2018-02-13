import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import simulatorOps.utils as utils
from simulatorOps.abstractOp import AbstractOp, ExecutionException

class SwapOp(AbstractOp):
    saveStateKeys = frozenset(("condition",
                                "byte", "rm", "rd", "rn"))

    def __init__(self):
        super().__init__()
        self._type = utils.InstrType.swap

    def decode(self):
        instrInt = self.instrInt
        if not (utils.checkMask(instrInt, (7, 4, 24), (27, 26, 25, 23, 21, 20, 11, 10, 9, 8, 6, 5))):
            raise ExecutionException("Le bytecode à cette adresse ne correspond à aucune instruction valide (10)", 
                                        internalError=False)

        # Retrieve the condition field
        self._decodeCondition()
        
        self.byte = bool(instrInt & (1 << 22))
        self.rm = instrInt & 0xF
        self.rd = (instrInt >> 12) & 0xF
        self.rn = (instrInt >> 16) & 0xF


    def explain(self, simulatorContext):
        self.resetAccessStates()
        bank = simulatorContext.regs.mode
        simulatorContext.regs.deactivateBreakpoints()
        
        self._nextInstrAddr = -1

        addr = simulatorContext.regs[self.rn]
        
        disassembly = "SWP"
        description = "<ol>\n"
        disCond, descCond = self._explainCondition()
        description += descCond
        disassembly += disCond
        sizedesc = "1 octet" if self.byte else "4 octets"

        self._readregs |= utils.registerWithCurrentBank(self.rn, bank)
        self._readregs |= utils.registerWithCurrentBank(self.rm, bank)
        self._writeregs |= utils.registerWithCurrentBank(self.rd, bank)

        description += "<li>Lit {} à partir de l'adresse contenue dans {}</li>\n".format(sizedesc, utils.regSuffixWithBank(self.rn, bank))
        if self.byte:
            disassembly += "B"
            description += "<li>Écrit l'octet le moins significatif du registre {} à l'adresse contenue dans {}</li>\n".format(utils.regSuffixWithBank(self.rm, bank), utils.regSuffixWithBank(self.rn, bank))
            description += "<li>Écrit l'octet le moins significatif de la valeur originale en mémoire dans {}</li>\n".format(utils.regSuffixWithBank(self.rd, bank))
            self._readmem = set([addr])
            self._writemem = set([addr])
        else:
            description += "<li>Écrit la valeur du registre {} à l'adresse contenue dans {}</li>\n".format(utils.regSuffixWithBank(self.rm, bank), utils.regSuffixWithBank(self.rn, bank))
            description += "<li>Écrit dans {} la valeur originale de l'adresse contenue dans {}</li>\n".format(utils.regSuffixWithBank(self.rd, bank), utils.regSuffixWithBank(self.rn, bank))
            self._readmem = set(range(addr, addr+4))
            self._writemem = set(range(addr, addr+4))

        disassembly += " R{}, R{}, [R{}]".format(self.rd, self.rm, self.rn)
        description += "</ol>"
        simulatorContext.regs.reactivateBreakpoints()
        return disassembly, description
    
    def execute(self, simulatorContext):
        if not self._checkCondition(simulatorContext.regs):
            # Nothing to do, instruction not executed
            self.countExecConditionFalse += 1
            return
        self.countExec += 1

        addr = simulatorContext.regs[self.rn]
        s = 1 if self.byte else 4
        m = simulatorContext.mem.get(addr, size=s)
        if m is None:       # No such address in the mapped memory, we cannot continue
            raise ExecutionException("Tentative de lecture de {} octets à partir de l'adresse {} invalide : mémoire non initialisée".format(s, addr))
        valMem = struct.unpack("<B" if self.byte else "<I", m)[0]

        # We write to the memory before writing the register in case where rd==rm
        valWrite = simulatorContext.regs[self.rm]
        simulatorContext.mem.set(addr, valWrite, size=1 if self.byte else 4)

        simulatorContext.regs[self.rd] = valMem
