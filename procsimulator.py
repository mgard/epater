from enum import Enum
from collections import defaultdict

from settings import getSetting

class SimulatorError(Exception):
    def __init__(self, desc):
        self.desc = desc
    def __str__(self):
        return self.desc

class Breakpoint(Exception):
    def __init__(self, addr):
        self.a = addr
    def __str__(self):
        return "Breakpoint {} atteint!".format(self.a)

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

    def __init__(self, memcontent, initval=0):
        self.size = size
        self.initval = initval
        self.history = None
        self.startAddr = memcontent['__MEMINFOSTART']
        self.endAddr = memcontent['__MEMINFOEND']
        self.maxAddr = max(self.endAddr.values())
        assert len(self.startAddr) == len(self.endAddr)

        self.data = {k:bytearray(memcontent[k]) for k in self.startAddr.keys()}

        # Maps address to an integer 'n'. The integer n allows to determine if the breakpoint should be
        # used or not, in the same way of Unix permissions.
        # If n & 4, then it is active for each read operation
        # If n & 2, then it is active for each write operation
        self.breakpoints = defaultdict(int)

    def isInBound(self, addr, strict=True):
        """
        Determine if *addr* is a valid address.
        :param addr: The address we want to check
        :param strict: If True, then mark as invalid uninitialized address (like the one between two sections). Else,
        simply check for the maximum and minimum value of the whole memory
        :return: A boolean telling whether *addr* is valid or not
        """
        if addr < 0 or addr > self.maxAddr - 3:
            return False
        if strict:
            for sec in self.startAddr.keys():
                if self.startAddr[sec] < addr < self.endAddr[sec] - 3:
                    return True
            return False
        return True

    def get(self, addr):
        if not isInBound(addr):
            raise SimulatorError("Adresse 0x{:X} invalide (devrait se situer entre 0x{:X} et 0x{:X})".format(addr, 0, self.size-3))
        if self.breakpoints[addr] & 4:
            raise Breakpoint(addr)
        return self.data[addr:addr+4]

    def set(self, addr, val):
        if not isInBound(addr):
            raise SimulatorError("Adresse 0x{:X} invalide (devrait se situer entre 0x{:X} et 0x{:X})".format(addr, 0, self.size-3))
        if self.breakpoints[addr] & 2:
            raise Breakpoint(addr)
        self.data[addr:addr+4] = val




class SimState(Enum):
    undefined = -1
    uninitialized = 0
    ready = 1
    started = 2
    stopped = 3
    finished = 4

class Simulator:

    def __init__(self, memorycontent):
        self.proc = Processor()
        self.mem = Memory(memorycontent)
        self.state = SimState.uninitialized

    def _printState(self):
        """
        Debug function
        :return:
        """
        pass

