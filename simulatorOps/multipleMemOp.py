import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import simulatorOps.utils as utils
from simulatorOps.abstractOp import AbstractOp, ExecutionException

class MultipleMemOp(AbstractOp):
    saveStateKeys = frozenset(("condition", ))      # TODO

    def __init__(self):
        super().__init__()
        self._type = utils.InstrType.multiplememop

    def decode(self):
        instrInt = self.instrInt
        if not (utils.checkMask(instrInt, (27,), (26, 25))):
            raise ExecutionException("masque de décodage invalide pour une instruction de type MULTIPLEMEM", 
                                        internalError=True)

        # Retrieve the condition field
        self._decodeCondition()
        
        # TODO

    def explain(self, simulatorContext):
        bank = simulatorContext.regs.mode
        simulatorContext.regs.deactivateBreakpoints()
        
        self._nextInstrAddr = -1
        
        disassembly = ""
        description = "<ol>\n"
        disCond, descCond = self._explainCondition()
        description += descCond

        # TODO

        description += "</ol>"
        simulatorContext.regs.reactivateBreakpoints()
        return disassembly, description
    
    def execute(self, simulatorContext):
        if not self._checkCondition(simulatorContext.regs):
            # Nothing to do, instruction not executed
            return

        # TODO
