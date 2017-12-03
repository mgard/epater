import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import simulatorOps.utils as utils

class ExecutionException(Exception):
    def __init__(self, text, internalError=False):
        self.text = text
        self.internal = internalError
    
    def __str__(self):
        if self.internal:
            return "Erreur interne : " + self.text
        else:
            return self.text

class AbstractOp:
    saveStateKeys = frozenset()

    def __init__(self):
        self._type = utils.InstrType.undefined
        self._nextInstrAddr = -1
        self._readflags = set()
        self._writeflags = set()
        self._readregs = set()
        self._writeregs = set()
        self._readmem = set()
        self._writemem = set()
        self.pcmodified = False

    def setBytecode(self, bytecode):
        assert len(bytecode) == 4 # 32 bits
        self.bc = bytecode

        # It's easier to work with integer objects when it comes to bit manipulation
        self.instrInt = struct.unpack("<I", bytecode)[0]

    def decode(self):
        raise NotImplementedError()

    def _decodeCondition(self):
        # Retrieve the condition field
        # We must handle potential invalid condition code (instrInt >> 28 == 15)
        self.condition = utils.conditionMappingR.get(self.instrInt >> 28, None)
        self.conditionValid = self.condition is not None

    def _explainCondition(self):
        # Since all instructions can be conditional, we can put a generic
        # implementation of the condition explanation here
        if self.condition == 'AL':
            return "", ""
        return self.condition, "<li>Vérifie si la condition {} est remplie</li>\n".format(self.condition)

    def _checkCondition(self, flags):
        # Since all instructions can be conditional, we can put a generic
        # implementation of the condition verification (before execution) here
        cond = self.condition
        self._readflags = utils.conditionFlagsMapping[cond]

        # Check condition
        # Warning : here we check if the condition is NOT met, hence we use the
        # INVERSE of the actual condition
        # See Table 4-2 of ARM7TDMI data sheet as reference of these conditions
        if (cond == "EQ" and not flags.Z or
            cond == "NE" and flags.Z or
            cond == "CS" and not flags.C or
            cond == "CC" and flags.C or
            cond == "MI" and not flags.N or
            cond == "PL" and flags.N or
            cond == "VS" and not flags.V or
            cond == "VC" and flags.V or
            cond == "HI" and (not flags.C or flags.Z) or
            cond == "LS" and (flags.C and not flags.Z) or
            cond == "GE" and not flags.V == flags.N or
            cond == "LT" and flags.V == flags.N or
            cond == "GT" and (flags.Z or flags.V != flags.N) or
            cond == "LE" and (not flags.Z and flags.V == flags.N)):
            return False
        
        # Else, the condition is true (including AL)
        return True
    
    def explain(self):
        raise NotImplementedError()
    
    def execute(self):
        raise NotImplementedError()

    @property
    def affectedRegs(self):
        return self._readregs, self._writeregs

    @property
    def affectedMem(self):
        return self._readmem, self._writemem

    @property
    def affectedFlags(self):
        return self._readflags, self._writeflags

    @property
    def nextAddressToExecute(self):
        return self._nextInstrAddr

    @property
    def instructionType(self):
        return self._type

    def saveState(self):
        # Each children class must define a saveStateKeys attribute
        return {k:v for k,v in self.__dict__.items() if k in self.saveStateKeys}

    def restoreState(self, state):
        self.__dict__.update(state)