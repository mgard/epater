import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import simulatorOps.utils as utils
from simulatorOps.abstractOp import AbstractOp, ExecutionException

class SoftInterruptOp(AbstractOp):
    saveStateKeys = frozenset(("condition", "datauser"))

    def __init__(self):
        super().__init__()
        self._type = utils.InstrType.softinterrupt

    def decode(self):
        instrInt = self.instrInt
        if not (utils.checkMask(instrInt, (24, 25, 26, 27), ())):
            raise ExecutionException("masque de décodage invalide pour une instruction de type SOFTINT", 
                                        internalError=True)

        # Retrieve the condition field
        self._decodeCondition()
        self.datauser = instrInt & 0xFFFFFF

    def explain(self, simulatorContext):
        self.resetAccessStates()
        bank = simulatorContext.regs.mode
        simulatorContext.regs.deactivateBreakpoints()
        
        description = "<ol>\n"
        disCond, descCond = self._explainCondition()
        description += descCond
        description += "<li>Changement de banque de registres vers SVC</li>\n"
        description += "<li>Copie du CPSR dans le SPSR_svc</li>\n"
        description += "<li>Copie de PC dans LR_svc</li>\n"
        description += "<li>Assignation de 0x08 dans PC</li>\n"
        disassembly = "SVC{} 0x{:X}".format(disCond, self.datauser)
        description += "</ol>"
        simulatorContext.regs.reactivateBreakpoints()
        return disassembly, description
    
    def execute(self, simulatorContext):
        if not self._checkCondition(simulatorContext.regs):
            # Nothing to do, instruction not executed
            self.countExecConditionFalse += 1
            return
        self.countExec += 1

        # We enter a software interrupt
        keepCPSR = simulatorContext.regs.CPSR
        simulatorContext.regs.mode = "SVC"                  # Set the register bank
        simulatorContext.regs.SPSR = keepCPSR               # Save the CPSR in the current SPSR
        # Does entering SVC interrupt deactivate IRQ and/or FIQ?
        simulatorContext.regs[14] = simulatorContext.regs[15]
        simulatorContext.regs[15] = 0x08                    # Entrypoint for the SVC
        self.pcmodified = True
