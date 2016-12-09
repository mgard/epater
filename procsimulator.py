import operator
import struct
from enum import Enum
from collections import defaultdict

from settings import getSetting
from instruction import BytecodeToInstrInfos, InstrType


def wrapAroundUint32(val):
    if val > 2**32-1:
        val -= 2**32
    elif val < 0:
        val += 2**32
    return val


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
        self.history = []
        self.breakpoint = 0

    def get(self):
        if self.breakpoint & 4:
            raise Breakpoint("R{}".format(self.id))
        return self.val

    def set(self, val, mayTriggerBkpt=True):
        val = wrapAroundUint32(val)
        if mayTriggerBkpt and self.breakpoint & 2:
            raise Breakpoint("R{}".format(self.id))
        self.history.append(val)
        self.val = val


class Flag:

    def __init__(self, name):
        self.name = name
        self.val = False
        self.breakpoint = 0

    def __bool__(self):
        if self.breakpoint & 4:
            raise Breakpoint(self.name)
        return self.val

    def get(self):
        return

    def set(self, val, mayTriggerBkpt=True):
        if mayTriggerBkpt and self.breakpoint & 2:
            raise Breakpoint(self.name)
        self.val = val


class Memory:

    def __init__(self, memcontent, initval=0):
        self.size = sum(len(b) for b in memcontent)
        self.initval = initval
        self.history = []
        self.startAddr = memcontent['__MEMINFOSTART']
        self.endAddr = memcontent['__MEMINFOEND']
        self.maxAddr = max(self.endAddr.values())
        assert len(self.startAddr) == len(self.endAddr)

        self.data = {k:bytearray(memcontent[k]) for k in self.startAddr.keys()}
        self.initdata = self.data.copy()

        # Maps address to an integer 'n'. The integer n allows to determine if the breakpoint should be
        # used or not, in the same way of Unix permissions.
        # If n & 4, then it is active for each read operation
        # If n & 2, then it is active for each write operation
        # If n & 1, then it is active for each exec operation (namely, an instruction load)
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
                return sec, addr - self.startAddr[sec]
        return None

    def get(self, addr, size=4, execMode=False):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            raise SimulatorError("Adresse 0x{:X} invalide".format(addr))

        for offset in range(size):
            if (execMode and self.breakpoints[addr+offset]) & 1 or self.breakpoints[addr+offset] & 4:
                raise Breakpoint(addr+offset)

        sec, offset = resolvedAddr
        return self.data[sec][offset:offset+size]

    def set(self, addr, val, size=4):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            raise SimulatorError("Adresse 0x{:X} invalide".format(addr))

        for offset in range(size):
            if self.breakpoints[addr+offset] & 2:
                raise Breakpoint(addr+offset)

        sec, offset = resolvedAddr
        val = wrapAroundUint32(val)
        self.history.append((sec, offset, size, val))
        self.data[sec][offset:offset+size] = val

    def serialize(self):
        """
        Serialize the memory, useful to be displayed.
        """
        sorted_mem = sorted(self.startAddr.items(), key=operator.itemgetter(1))
        ret_val = bytearray()
        for sec, start in sorted_mem:
            padding_size = start - len(ret_val)
            ret_val += bytearray('\0' * padding_size, 'utf-8')

            ret_val += self.data[sec]

            padding_size = self.endAddr[sec] - start - len(self.data[sec])
            ret_val += bytearray('\0' * padding_size, 'utf-8')
        return ret_val


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

        self.stepMode = None
        self.stepCondition = 0

        self.flags = {'Z': Flag('Z'),
                      'V': Flag('V'),
                      'C': Flag('C'),
                      'N': Flag('N')}

    def reset(self):
        self.regs[15].set(0)
        self.state = SimState.ready

    def _printState(self):
        """
        Debug function
        :return:
        """
        pass

    def isStepDone(self):
        # TODO : a breakpoint always reset this
        if self.stepMode == "forward":
            if self.stepCondition == 2:
                # The instruction was a function call
                # Now the step forward becomes a step out
                self.stepMode = "out"
                self.stepCondition = 1
            else:
                return True
        if self.stepMode == "out":
            return self.stepCondition == 0
        return True


    def setStepCondition(self, stepMode):
        assert stepMode in ("out", "forward")
        self.stepMode = stepMode
        self.stepCondition = 1


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
        bc = bytes(self.mem.get(addr, execMode=True))    # Memory is little endian, so we convert it back to a more usable form

        # Decode it
        t, regs, cond, misc = BytecodeToInstrInfos(bc)
        workingFlags = {}

        # Check condition
        # Warning : here we check if the condition is NOT met, hence we use the
        # INVERSE of the actual condition
        # See Table 4-2 of ARM7TDMI data sheet as reference of these conditions
        if cond == "EQ" and not self.flags['Z'] or \
            cond == "NE" and self.flags['Z'] or \
            cond == "CS" and not self.flags['C'] or \
            cond == "CC" and self.flags['C'] or \
            cond == "MI" and not self.flags['N'] or \
            cond == "PI" and self.flags['N'] or \
            cond == "VS" and not self.flags['V'] or \
            cond == "VC" and self.flags['V'] or \
            cond == "HI" and (not self.flags['C'] or self.flags['Z']) or \
            cond == "LS" and (self.flags['C'] and not self.flags['Z']) or \
            cond == "GE" and not self.flags['V'] == self.flags['N'] or \
            cond == "LT" and self.flags['V'] == self.flags['N'] or \
            cond == "GT" and (self.flags['Z'] or not self.flags['V'] == self.flags['N']) or \
            cond == "LE" and (not self.flags['Z'] and self.flags['V'] == self.flags['N']):
            # Condition not met, return
            return

        # Execute it
        if t == InstrType.branch:
            if misc['L']:       # Link
                self.regs[14].set(self.regs[15].get()+4)
                self.stepCondition += 1         # We are entering a function, we log it (useful for stepForward and stepOut)
            if misc['mode'] == 'imm':
                print(misc['offset'])
                self.regs[15].set(self.regs[15].get() + misc['offset'] - 4)
            else:   # BX
                self.regs[15].set(self.regs[misc['offset']].get() - 4)
                self.stepCondition -= 1         # We are returning from a function, we log it (useful for stepForward and stepOut)

        elif t == InstrType.memop:
            baseval = self.regs[misc['base']].get()
            addr = baseval
            if misc['imm']:
                addr += misc['sign'] * misc['offset']
            else:
                sval, _ = self._shiftVal(self.regs[misc['offset'][0]].get(), misc['offset'][1])
                addr += misc['sign'] * sval

            realAddr = addr if misc['pre'] else baseval
            if misc['mode'] == 'LDR':
                res = struct.unpack("<I", self.mem.get(realAddr, size=1 if misc['byte'] else 4))[0]
                self.regs[misc['rd']].set(res)
            else:       # STR
                self.mem.set(realAddr, self.regs[misc['rd']].get(), size=1 if misc['byte'] else 4)

            if misc['writeback']:
                self.regs[misc['base']].set(addr)

        elif t == InstrType.dataop:
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
                # TODO : update flags
            elif misc['opcode'] in ("EOR", "TEQ"):
                res = op1 ^ op2
                # TODO : update flags
            elif misc['opcode'] in ("SUB", "CMP"):
                res = op1 - op2
                # TODO : update flags
            elif misc['opcode'] == "RSB":
                res = op2 - op1
            elif misc['opcode'] in ("ADD", "CMN"):
                res = op1 + op2
                workingFlags['C'] = bool(res & (1 << 32))
                if not bool((op1 & 0x80000000) ^ (op2 & 0x80000000)):
                    workingFlags['V'] = not bool((op1 & 0x80000000) ^ (res & 0x80000000))
            elif misc['opcode'] == "ADC":
                res = op1 + op2 + int(self.flags['C'])
                workingFlags['C'] = bool(res & (1 << 32))
                if not bool((op1 & 0x80000000) ^ (op2 & 0x80000000)):
                    workingFlags['V'] = not bool((op1 & 0x80000000) ^ (res & 0x80000000))
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
            else:
                assert False, "Bad data opcode : " + misc['opcode']

            if res == 0:
                workingFlags['Z'] = True
            if res < 0:
                workingFlags['N'] = True

            if misc['setflags']:
                for flag in workingFlags:
                    self.flags[flag].set(workingFlags[flag])
            if misc['opcode'] not in ("TST", "TEQ", "CMP", "CMN"):
                # We actually write the result
                self.regs[destrd].set(res)

    def nextInstr(self):
        self.execInstr(self.regs[15].get())
        self.regs[15].set(self.regs[15].get()+4)        # PC = PC + 4


