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
            if self.startAddr[sec] <= addr < self.endAddr[sec] - (size-1):
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

    def formatMemToDisplay(self):
        pass


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

    def reset(self):
        self.regs[15].set(0)
        self.state = SimState.ready

    def _printState(self):
        """
        Debug function
        :return:
        """
        pass

    def _shiftVal(self, val, shiftInfo):
        shiftamount = self.regs[shiftInfo[2]].get() & 0xF if shiftInfo[1] == 'reg' else shiftInfo[2]
        carryOut = 0
        if shiftInfo[0] == "LSL":
            carryOut = (val >> (32-shiftamount)) & 1
            val = (val << shiftamount) & 0xFFFFFFFF
        elif shiftInfo[0] == "LSR":
            carryOut = (val >> (shiftamount-1)) & 1
            val = (val >> shiftamount) & 0xFFFFFFFF
        elif shiftInfo[0] == "ASR":
            carryOut = (val >> (shiftamount-1)) & 1
            firstBit = (val >> 31) & 1
            val = ((val >> shiftamount) & 0xFFFFFFFF) | (2**(shiftamount+1) << (32-shiftamount))
        elif shiftInfo[0] == "ROR":
            if shiftamount == 0:
                # The form of the shift field which might be expected to give ROR #0 is used to encode
                # a special function of the barrel shifter, rotate right extended (RRX).
                carryOut = val & 1
                val = (val >> 1) | (int(self.flags['C']) << 31)
            else:
                carryOut = (val >> (shiftamount-1)) & 1
                val = ((val & (2**32-1)) >> shiftamount%32) | (val << (32-(shiftamount%32)) & (2**32-1))
        return carryOut, val


    def execInstr(self, addr):
        """
        Execute one instruction
        :param addr: Address of the instruction in memory
        :return:
        This function may throw a SimulatorError exception if there's an error, or a Breakpoint exception,
        in which case it is not an error but rather a Breakpoint reached.
        """
        # Retrieve instruction from memory
        bc = bytes(self.mem.get(addr))[::-1]    # Memory is little endian, so we convert it back to a more usable form

        # Decode it
        t, regs, cond, misc = BytecodeToInstrInfos(bc)
        workingFlags = self.flags.copy()

        # Execute it
        if t == InstrType.dataop:
            # Get first operand value
            op1 = self.regs[misc['rn']].get()
            # Get second operand value
            if misc['imm']:
                op2 = misc['op2'][0]
                if misc['op2'][1][2] != 0:
                    _, op2 = self._shiftVal(op2, misc['op2'][1])
            else:
                op2 = self.regs[misc['op2'][0]].get()
                carry, op2 = self._shiftVal(op2, misc['op2'][1])
                workingFlags['C'] = bool(carry)

            # Get destination register and write the result
            destrd = misc['rd']

            if misc['opcode'] in ("AND", "TST"):
                res = op1 & op2
            elif misc['opcode'] in ("EOR", "TEQ"):
                res = op1 ^ op2
            elif misc['opcode'] in ("SUB", "CMP"):
                res = op1 - op2
            elif misc['opcode'] == "RSB":
                res = op2 - op1
            elif misc['opcode'] in ("ADD", "CMN"):
                res = op1 + op2
                workingFlags['C'] = bool(destrd & (1 << 32))
            elif misc['opcode'] == "ADC":
                res = op1 + op2 + int(self.flags['C'])
                workingFlags['C'] = bool(destrd & (1 << 32))
            elif misc['opcode'] == "SBC":
                res = op1 - op2 + int(self.flags['C']) - 1
            elif misc['opcode'] == "RSC":
                res = op2 - op1 + int(self.flags['C']) - 1
            elif misc['opcode'] == "ORR":
                res = op1 | op2
            elif misc['opcode'] == "MOV":
                res = op2
            elif misc['opcode'] == "BIC":
                res = op1 & ~op2     # Bit clear?
            elif misc['opcode'] == "MVN":
                res = ~op2

            if res == 0:
                workingFlags['Z'] = True
            if res < 0:
                workingFlags['N'] = True

            # TODO Flag V

            if misc['setflags']:
                self.flags = workingFlags
            if misc['opcode'] not in ("TST", "TEQ", "CMP", "CMN"):
                # We actually write the result
                self.regs[destrd].set(res)

    def nextInstr(self):
        self.execInstr(self.regs[15].get())
        self.regs[15].set(self.regs[15].get()+4)        # PC = PC + 4


