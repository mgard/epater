import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque

from settings import getSetting

class Breakpoint(Exception):

    def __init__(self, component, mode):
        self.cmp = component
        self.mode = mode


class Component:
    
    def __init__(self, history):
        self.history = history

    def stepBack(self, state):
        raise NotImplementedError


class _Register:

    def __init__(self, n, val=0, altname=None):
        self.id = n
        self.val = val
        self.altname = altname
        self.breakpoint = 0

    @property
    def name(self):
        return "R{}".format(self.id) if self.altname is None else self.altname


class Registers(Component):
    flag2index = {'N': 31, 'Z': 30, 'C': 29, 'V': 28, 'I': 7, 'F': 6}
    index2flag = {v:k for k,v in flag2index.items()}
    mode2bits = {'User': 16, 'FIQ': 17, 'IRQ': 18, 'SVC': 19}       # Other modes are not supported
    bits2mode = {v:k for k,v in mode2bits.items()}

    def __init__(self, history):
        super().__init__(history)
        self.history.registerObject(self)

        # For each bank we create 17 registers (some of them being shared)
        # The "17th" register is the SPSR for this mode, which should never be
        # directly accessed by the user
        # In User mode, since there is no SPSR, no additional register is created

        # Create user registers
        regs = [Register(i) for i in range(16)]
        regs[13].altname = "SP"
        regs[14].altname = "LR"
        regs[15].altname = "PC"
        self.banks['User'] = regs

        # Create FIQ registers
        regsFIQ = regs[:8]          # R0-R7 are shared
        regsFIQ.extend(Register(i) for i in range(8, 15))        # R8-R14 are exclusive
        regsFIQ[13].altname = "SP"
        regsFIQ[14].altname = "LR"
        regsFIQ.append(regs[15])    # PC is shared
        regsFIQ.append(Register(16))
        regsFIQ[16].altname = "SPSR"
        self.banks['FIQ'] = regsFIQ

        # Create IRQ registers
        regsIRQ = regs[:13]         # R0-R12 are shared
        regsIRQ.extend(Register(i) for i in range(13, 15))        # R13-R14 are exclusive
        regsIRQ[13].altname = "SP"
        regsIRQ[14].altname = "LR"
        regsIRQ.append(regs[15])    # PC is shared
        regsIRQ.append(Register(16))
        regsIRQ[16].altname = "SPSR"
        self.banks['IRQ'] = regsIRQ

        # Create SVC registers (used with software interrupts)
        regsSVC = regs[:13]  # R0-R12 are shared
        regsSVC.extend(Register(i) for i in range(13, 15))  # R13-R14 are exclusive
        regsIRQ[13].altname = "SP"
        regsIRQ[14].altname = "LR"
        regsSVC.append(regs[15])  # PC is shared
        regsSVC.append(Register(16))
        regsSVC[16].altname = "SPSR"
        self.banks['SVC'] = regsSVC

        # CPSR is always used, so we keep it apart
        # By default, we start in user mode, with no flags
        self.regCPSR = self.mode2bits['User']

    @property
    def currentMode(self):
        k = self.regCPSR & 0x1F
        assert k in self.bits2mode, "Invalid processor mode : {}".format(k)
        return self.bits2mode[k]

    def setMode(self, mode):
        if mode not in self.mode2bits:
            raise KeyError
        oldCPSR = self.regCPSR
        self.regCPSR &= 0xFFFFFFE0                  # Reset the mode
        self.regCPSR |= self.mode2bits[mode]        # Set the mode wanted
        self.history.signalChange(self, {(currentBank, "CPSR"): (oldCPSR, self.regCPSR)})

    def __getitem__(self, idx):
        currentBank = self.currentMode
        if isinstance(idx, int):
            # Register
            if self.banks[currentBank][idx].breakpoint & 4:
                raise Breakpoint("register", 'r')
            return self.banks[currentBank][idx].val
        elif idx in ("CPSR", "SPSR"):
            if idx == "SPSR":
                if currentBank == "User":
                    pass    # TODO raise an exception, there is no SPSR in User mode
                return self[16]
            else:   # CPSR
                return self.regCPSR
        else:
            # Flag
            return bool((self.regCPSR >> self.flag2index[idx]) & 0x1)

    def __setitem__(self, idx, val):
        currentBank = self.currentMode
        if isinstance(idx, int):
            # Register
            if self.banks[currentBank][idx].breakpoint & 2:
                raise Breakpoint("register", 'w')
            
            oldValue, newValue = self.banks[currentBank][idx].val, val & 0xFFFFFFFF
            self.history.signalChange(self, {(currentBank, idx): (oldValue, newValue)})
            self.banks[currentBank][idx].val = newValue
        elif idx in ("CPSR", "SPSR"):
            if idx == "SPSR":
                if currentBank == "User":
                    pass    # TODO raise an exception, there is no SPSR in User mode
                self[16] = val
            else:   # CPSR
                oldValue, newValue = self.regCPSR, val & 0xFFFFFFFF
                self.regCPSR = val
                self.history.signalChange(self, {(currentBank, "CPSR"): (oldValue, newValue)})
        else:
            # Flag
            self.setFlag(idx, val)
    
    def setFlag(self, flag, value, mayTriggerBkpt=True):
        flag = flag.upper()
        if flag not in self.flag2index:
            raise KeyError

        if mayTriggerBkpt and self.breakpoints[flag] & 2:
            raise Breakpoint("flags", 'w')
        
        oldCPSR = self.regCPSR
        if value:   # We set the flag
            self.regCPSR |= 1 << self.flag2index[flag]
        else:       # We clear the flag
            self.regCPSR &= 0xFFFFFFFF - (1 << self.flag2index[flag])

        self.history.signalChange(self, {(currentBank, "CPSR"): (oldCPSR, self.regCPSR)})
        
    def stepBack(self, state):
        for k, val in state:
            bank, reg = k
            if reg == "CPSR":
                self.regCPSR = reg
            else:
                self.banks[bank][reg] = val[0]


class Memory(Component):
    
    def __init__(self, history, memcontent, initval=0):
        super().__init__(history)
        self.history.registerObject(self)

        self.size = sum(len(b) for b in memcontent)
        self.initval = initval
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
        for sec in self.startAddr.keys():       # TODO : optimize this loop out
            if self.startAddr[sec] <= addr < self.endAddr[sec] - (size-1):
                return sec, addr - self.startAddr[sec]
        return None

    
    def stepBack(self, state):
        pass
