from enum import Enum

from settings import getSetting


class Register:

    def __init__(self, n, val=0, altname=None):
        self.id = n
        self.val = val
        self.altname = altname


class Processor:
    pass

class Memory:
    pass

class SimState(Enum):
    undefined = -1
    uninitialized = 0
    ready = 1
    started = 2
    stopped = 3
    finished = 4

class Simulator:

    def __init__(self):
        self.proc = Processor()
        self.mem = Memory
        self.state = SimState.uninitialized