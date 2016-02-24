from enum import Enum

from settings import getSetting


class Register:

    def __init__(self, n, val=0, altname=None):
        self.id = n
        self.val = val
        self.altname = altname
        self.history = None


class Processor:

    def __init__(self):
        self.regs = [Register(i) for i in range(16)]
        self.regs[13].altname = "SP"
        self.regs[14].altname = "LR"
        self.regs[15].altname = "PC"



class Memory:

    def __init__(self, size):
        self.size = size
        self.history = None

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
        self.mem = Memory()
        self.state = SimState.uninitialized

    def _printState(self):
        """
        Debug function
        :return:
        """
        pass

