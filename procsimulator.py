from enum import Enum
from collections import defaultdict

from settings import getSetting
from instruction import BytecodeToInstrInfos, InstrType


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
        self.breakpoint = 0

    def get(self):
        if self.breakpoint & 4:
            raise Breakpoint("R{}".format(id))
        return self.val

    def set(self, val):
        if self.breakpoint & 2:
            raise Breakpoint("R{}".format(id))
        self.val = val


class Memory:

    def __init__(self, memcontent, initval=0):
        self.size = sum(len(b) for b in memcontent)
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

    def _getRelativeAddr(self, addr, size):
        """
        Determine if *addr* is a valid address, and return a tuple containing the section
        and offset of this address.
        :param addr: The address we want to check
        :return: None if the address is invalid. Else, a tuple of two elements, the first being the
        section used and the second the offset relative from the start of this section.
        """
        if addr < 0 or addr > self.maxAddr - (size-1):
            return None
        for sec in self.startAddr.keys():
            if self.startAddr[sec] < addr < self.endAddr[sec] - (size-1):
                return (sec, addr - self.startAddr[sec])
        return None

    def get(self, addr, size=4):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            raise SimulatorError("Adresse 0x{:X} invalide".format(addr))
        if self.breakpoints[addr] & 4:
            raise Breakpoint(addr)
        sec, offset = resolvedAddr
        return self.data[sec][offset:offset+size]

    def set(self, addr, val, size=4):
        resolvedAddr = self._getRelativeAddr(addr)
        if resolvedAddr is None:
            raise SimulatorError("Adresse 0x{:X} invalide".format(addr))
        if self.breakpoints[addr] & 2:
            raise Breakpoint(addr)
        sec, offset = resolvedAddr
        self.data[sec][offset:offset+size] = val


class SimState(Enum):
    undefined = -1
    uninitialized = 0
    ready = 1
    started = 2
    stopped = 3
    finished = 4

class Simulator:

    def __init__(self, memorycontent):
        self.state = SimState.uninitialized
        self.mem = Memory(memorycontent)

        self.regs = [Register(i) for i in range(16)]
        self.regs[13].altname = "SP"
        self.regs[14].altname = "LR"
        self.regs[15].altname = "PC"

        self.flags = {'Z': False,
                      'V': False,
                      'C': False,
                      'N': False}

    def _printState(self):
        """
        Debug function
        :return:
        """
        pass

    def execInstr(self, addr):
        """
        Execute one instruction
        :param addr: Address of the instruction in memory
        :return:
        This function may throw a SimulatorError exception if there's an error, or a Breakpoint exception,
        in which case it is not an error but rather a Breakpoint reached.
        """
        # Retrieve instruction from memory
        bc = bytes(self.mem.get(addr))

        # Decode it
        t, regs, cond, misc = BytecodeToInstrInfos(bc)

        # Execute it
        if t == InstrType.dataop:
            pass

