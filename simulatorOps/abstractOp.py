import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import utils

class AbstractOp:

    def __init__(self, bytecode):
        assert len(bytecode) == 4 # 32 bits
        self.bc = bytecode

        # It's easier to work with integer objects when it comes to bit manipulation
        self.instrInt = struct.unpack("<I", bytecode)[0]
        self.decodeError = False
        self._type = utils.InstrType.undefined

    def decode(self):
        raise NotImplementedError()
    
    def explain(self):
        raise NotImplementedError()
    
    def execute(self):
        raise NotImplementedError()

    @property
    def affectedRegs(self):
        return ()

    @property
    def affectedMem(self):
        return ()

    @property
    def affectedFlags(self):
        return ()

    @property
    def instructionType(self):
        return self._type if not self.decodeError else utils.InstrType.undefined