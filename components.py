import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque

from settings import getSetting

class Breakpoint(Exception):
    """
    Indicates that a breakpoint or an error occured while executing 
    the requested operation.

    This exception object holds details about this breakpoint:
    * `cmp` contains a string describing the subsystem where the
        breakpoint occured. Can be "memory", "register" or "flags".
    * `mode` is an integer indicating the type of breakpoint.
        if mode & 1, then it indicates an _execution_ breakpoint
        if mode & 2, then it indicates a _write_ breakpoint
        if mode & 4, then it indicates a _read_ breakpoint
        if mode & 8, then it indicates an _error_ with the request
       The last type is not an actual breakpoint, but is nevertheless
       used to raise errors caused by the user behavior (and that
       should thus appropriately be displayed in the UI)
    * `info` is a field containing more information about the
        component which trigged the breakpoint.
        In the case of memory, this is the address where the
        breakpoint has occured.
        In the case of register, it is the register index.
        In the case of a flag, it is the flag letter (C, V, Z, or N)
    * `desc` is used in case of error (e.g. mode & 8) to provide a
        user-friendly description of the problem
    """

    def __init__(self, component, mode, info=None, desc=""):
        self.cmp = component
        self.mode = mode
        self.info = info
        self.desc = desc
    

class Component:
    
    def __init__(self, history):
        self.history = history

    def stepBack(self, state):
        raise NotImplementedError

    def getContext(self):
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
    """
    This object is a component holding all the information about the registers,
    including the control register (CPSR) and its backups (SPSR).
    As such, it is also the object dictating the current processor mode (User,
    FIQ, IRQ, SVC, etc.).

    To simplify the access to its components, this object automatically selects
    the appropriate register given the current bank. Many registers are aliased
    through different banks (this is done automatically by this class).

    The current processor mode (and so the current bank) can be retrieved or
    modified using the `mode` property. This entirely depends on the value of 
    CPSR, so if the content of this register is changed, the mode will 
    automatically follow.

    A register value can be retrieved or set using the item retrieval notation.
    The argument should be the _integer_ value of the register name (so, for
    instance, calling thisObject[0] returns or sets the value of R0, and
    thisObject[15] allows access to R15/PC). Only indices between 0 and 15
    inclusively are valid values, the comportement of the object in any other
    case is undefined.

    A flag value can be set or retrieved using the attribute notation. That is,
    thisObject.C returns (or sets) the state of the carry flag. Valid flag
    values are "C" (carry), "Z" (zero), "N" (negative), and "V" (overflow).

    The IRQ and FIQ flags can be retrieved or set using IRQ and FIQ properties.
    Remember that such flag set (=1) means that interrupts are _disabled_!

    CPSR register can be set or retrieved as a whole (as opposed to retrieve
    only some parts of it using the previously exposed API) using the "CPSR"
    property. Same thing applies to SPSR register, which is automatically tied
    to the current bank. It is an error to try to retrieve the SPSR register
    in user mode (since no such register exists).

    Usually, it is not advisable to modify directly CPSR, since many of its
    possible values are invalid. However, in some cases like restoring the
    context by copying SPSR into CPSR, this is the way to go.
    """
    flag2index = {'N': 31, 'Z': 30, 'C': 29, 'V': 28, 'I': 7, 'F': 6}
    index2flag = {v:k for k,v in flag2index.items()}
    mode2bits = {'User': 16, 'FIQ': 17, 'IRQ': 18, 'SVC': 19}       # Other modes are not supported
    bits2mode = {v:k for k,v in mode2bits.items()}

    def __init__(self, history):
        super().__init__(history)
        self.history.registerObject(self)
        self.bkptActive = True

        # For each bank we create 17 registers (some of them being shared)
        # The "17th" register is the SPSR for this mode, which should never be
        # directly accessed by the user
        # In User mode, since there is no SPSR, no additional register is created
        self.banks = {}

        # Create user registers
        regs = [_Register(i) for i in range(16)]
        regs[13].altname = "SP"
        regs[14].altname = "LR"
        regs[15].altname = "PC"
        self.banks['User'] = regs

        # Create FIQ registers
        regsFIQ = regs[:8]          # R0-R7 are shared
        regsFIQ.extend(_Register(i) for i in range(8, 15))        # R8-R14 are exclusive
        regsFIQ[13].altname = "SP"
        regsFIQ[14].altname = "LR"
        regsFIQ.append(regs[15])    # PC is shared
        regsFIQ.append(_Register(16))
        regsFIQ[16].altname = "SPSR"
        self.banks['FIQ'] = regsFIQ

        # Create IRQ registers
        regsIRQ = regs[:13]         # R0-R12 are shared
        regsIRQ.extend(_Register(i) for i in range(13, 15))        # R13-R14 are exclusive
        regsIRQ[13].altname = "SP"
        regsIRQ[14].altname = "LR"
        regsIRQ.append(regs[15])    # PC is shared
        regsIRQ.append(_Register(16))
        regsIRQ[16].altname = "SPSR"
        self.banks['IRQ'] = regsIRQ

        # Create SVC registers (used with software interrupts)
        regsSVC = regs[:13]  # R0-R12 are shared
        regsSVC.extend(_Register(i) for i in range(13, 15))  # R13-R14 are exclusive
        regsSVC[13].altname = "SP"
        regsSVC[14].altname = "LR"
        regsSVC.append(regs[15])  # PC is shared
        regsSVC.append(_Register(16))
        regsSVC[16].altname = "SPSR"
        self.banks['SVC'] = regsSVC

        # CPSR is always used, so we keep it apart
        # By default, we start in user mode, with no flags
        self.regCPSR = self.mode2bits['User']
        self.currentMode = "User"

        # Keep the breakpoints on the flags
        self.bkptFlags = {k:0 for k in self.flag2index.keys()}

    def getContext(self):
        c = {'CPSR': self.regCPSR}
        c.update(self.banks)
        return c

    @property
    def mode(self):
        return self.currentMode

    @mode.setter
    def mode(self, val):
        if val not in self.mode2bits:
            raise ValueError("Invalid mode '{}'".format(val))
        valCPSR = self.regCPSR & (0xFFFFFFFF - 0x1F)    # Clear mode
        valCPSR = self.regCPSR | self.mode2bits[val]
        self.history.signalChange(self, {(val, "CPSR"): (self.regCPSR, valCPSR)})
        self.regCPSR = valCPSR
        self.currentMode = val

    @property
    def CPSR(self):
        return self.regCPSR

    @CPSR.setter
    def CPSR(self, val):
        oldValue, newValue = self.regCPSR, val & 0xFFFFFFFF
        self.regCPSR = val
        self.currentMode = self.bits2mode[self.regCPSR & 0x1F]
        self.history.signalChange(self, {(self.mode, "CPSR"): (oldValue, newValue)})

    @property
    def SPSR(self):
        currentBank = self.currentMode
        if currentBank == "User":
            raise Breakpoint("register", 8, None, "Le registre SPSR n'existe pas en mode 'User'!")
        return self.banks[currentBank][16].val

    @SPSR.setter
    def SPSR(self, val):
        currentBank = self.currentMode
        if currentBank == "User":
            raise Breakpoint("register", 8, None, "Le registre SPSR n'existe pas en mode 'User'!")
        self.history.signalChange(self, {(self.mode, "SPSR"): (self[16], val)})
        self[16] = val

    @property
    def IRQ(self):
        return bool(self.regCPSR >> 7 & 1)

    @IRQ.setter
    def IRQ(self, val):
        oldCPSR = self.regCPSR
        currentBank = self.currentMode
        if val:
            self.regCPSR |= 1 << 7
        else:
            self.regCPSR &= 0xFFFFFFFF - (1 << 7)
        self.history.signalChange(self, {(currentBank, "CPSR"): (oldCPSR, self.regCPSR)})

    @property
    def FIQ(self):
        return bool(self.regCPSR >> 6 & 1)

    @FIQ.setter
    def FIQ(self, val):
        oldCPSR = self.regCPSR
        currentBank = self.currentMode
        if val:
            self.regCPSR |= 1 << 6
        else:
            self.regCPSR &= 0xFFFFFFFF - (1 << 6)
        self.history.signalChange(self, {(currentBank, "CPSR"): (oldCPSR, self.regCPSR)})

    @property
    def N(self):
        return bool(self.regCPSR & 0x80000000)

    @N.setter
    def N(self, val):
        self.setFlag("N", val)

    @property
    def Z(self):
        return bool(self.regCPSR & 0x40000000)

    @Z.setter
    def Z(self, val):
        self.setFlag("Z", val)

    @property
    def C(self):
        return bool(self.regCPSR & 0x20000000)

    @C.setter
    def C(self, val):
        self.setFlag("C", val)
    
    @property
    def V(self):
        return bool(self.regCPSR & 0x10000000)

    @V.setter
    def V(self, val):
        self.setFlag("V", val)

    def __getitem__(self, idx):
        currentBank = self.currentMode
        regHandle = self.banks[currentBank][idx]
        # Register
        if self.bkptActive and regHandle.breakpoint & 4:
            raise Breakpoint("register", 4, (currentBank, idx))
        return regHandle.val

    def getAllRegisters(self):
        # Helper function to get all registers from all banks at once
        # The result is returned as a dictionary of dictionary
        return {bname: {reg.id: reg.val for reg in bank} for bname, bank in self.banks.items()}

    def getRegister(self, bank, reg):
        # Get a register with a specific bank
        if self.bkptActive and self.banks[bank][reg].breakpoint & 4:
            raise Breakpoint("register", 4, (bank, reg))
        return self.banks[bank][reg].val

    def __setitem__(self, idx, val):
        self.setRegister(self.currentMode, idx, val)

    def setRegister(self, bank, reg, val, logToHistory=True):
        # In some cases, we want to set the register of a specific bank
        # The [] operator always uses the current bank, so this method
        # can be used in this specific case.
        # This may also be used if we don't want the change to be logged
        # in the history of the register (just set logToHistory to False).
        regHandle = self.banks[bank][reg]
        if self.bkptActive and regHandle.breakpoint & 2:
            raise Breakpoint("register", 2, (bank, reg))
        oldValue, newValue = self.banks[bank][reg].val, val & 0xFFFFFFFF

        if logToHistory:
            if reg < 8 or reg == 15:
                # Always aliased
                dchanges = {(b, reg): (oldValue, newValue) for b in self.banks}
            elif reg >= 13 or bank == "FIQ":
                # Never aliased
                dchanges = {(bank, reg): (oldValue, newValue)}
            else:
                # Aliased with everyone but FIQ
                dchanges = {(b, reg): (oldValue, newValue) for b in self.banks if b != "FIQ"}

            self.history.signalChange(self, dchanges)

        regHandle.val = newValue
    
    def setFlag(self, flag, value, mayTriggerBkpt=True, logToHistory=True):
        currentBank = self.currentMode

        try:
            bkptFlag = self.bkptFlags[flag]
        except KeyError:
            raise Breakpoint("flags", 8, flag)

        if self.bkptActive and mayTriggerBkpt and bkptFlag & 2:
            raise Breakpoint("flags", 2, flag)
        
        oldCPSR = self.regCPSR
        if value:   # We set the flag
            self.regCPSR |= 1 << self.flag2index[flag]
        else:       # We clear the flag
            self.regCPSR &= 0xFFFFFFFF - (1 << self.flag2index[flag])

        if logToHistory:
            self.history.signalChange(self, {(currentBank, "CPSR"): (oldCPSR, self.regCPSR)})

    def setAllFlags(self, flagsDict, mayTriggerBkpt=True):
        oldCPSR = self.regCPSR
        for flag, value in flagsDict.items():

            if self.bkptActive and mayTriggerBkpt and self.bkptFlags[flag] & 2:
                raise Breakpoint("flags", 2, flag)

            if value:   # We set the flag
                self.regCPSR |= 1 << self.flag2index[flag]
            else:       # We clear the flag
                self.regCPSR &= 0xFFFFFFFF - (1 << self.flag2index[flag])
        self.history.signalChange(self, {(self.currentMode, "CPSR"): (oldCPSR, self.regCPSR)})

    def deactivateBreakpoints(self):
        # Without removing them, do not trig on breakpoint until `reactivateBreakpoints`
        # is called. Useful for the decoding state, where we want to check the value of
        # a register or a flag without possibly trigging a breakpoint.
        self.bkptActive = False

    def reactivateBreakpoints(self):
        # See `deactivateBreakpoints`
        self.bkptActive = True

    def toggleBreakpointOnRegister(self, bank, regidx, modeOctal):
        # Toggle the value
        self.banks[bank][regidx].breakpoint ^= modeOctal

    def toggleBreakpointOnFlag(self, flag, modeOctal):
        # Toggle the value
        self.bkptFlags[flag] ^= modeOctal

    def setBreakpointOnRegister(self, bank, regidx, breakpointType):
        self.banks[bank][regidx].breakpoint = breakpointType

    def setBreakpointOnFlag(self, flag, breakpointType):
        self.bkptFlags[flag] = breakpointType

    def stepBack(self, state):
        # TODO what happens if we change mode at the same time we change a register?
        for k, val in state.items():
            bank, reg = k
            if reg == "CPSR":
                self.regCPSR = val[0]
            else:
                if reg == "SPSR":
                    reg = 16
                self.banks[bank][reg].val = val[0]


class Memory(Component):
    packformat = {1: "<B", 2: "<H", 4: "<I"}
    maskformat = {1: 0xFF, 2: 0xFFFF, 4: 0xFFFFFFFF}
    
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
        self.bkptActive = True

        # Maps address to an integer 'n'. The integer n allows to determine if the breakpoint should be
        # used or not, in the same way of Unix permissions.
        # If n & 4, then it is active for each read operation
        # If n & 2, then it is active for each write operation
        # If n & 1, then it is active for each exec operation (namely, an instruction load)
        self.breakpoints = defaultdict(int)

    def getContext(self):
        return self.data
    
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
    
    def get(self, addr, size=4, execMode=False, mayTriggerBkpt=True):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            if execMode:
                desc = "Tentative de lecture d'une instruction a une adresse non initialisée : {}".format(hex(addr))
            else:
                desc = "Accès mémoire en lecture fautif a l'adresse {}".format(hex(addr))
            raise Breakpoint("memory", 8, addr, desc)

        for offset in range(size):
            if self.bkptActive and execMode and self.breakpoints[addr+offset] & 1:
                raise Breakpoint("memory", 1, addr + offset)
            if self.bkptActive and mayTriggerBkpt and self.breakpoints[addr+offset] & 4:
                raise Breakpoint("memory", 4, addr + offset)

        sec, offset = resolvedAddr
        return self.data[sec][offset:offset+size]

    def set(self, addr, val, size=4, mayTriggerBkpt=True):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            raise Breakpoint("memory", 8, addr, "Accès invalide pour une écriture de taille {} à l'adresse {}".format(size, hex(addr)))

        for offset in range(size):
            if self.bkptActive and mayTriggerBkpt and self.breakpoints[addr+offset] & 2:
                raise Breakpoint("memory", 2, addr + offset)

        sec, offset = resolvedAddr
        val &= self.maskformat[size]
        valBytes = struct.pack(self.packformat[size], val)

        dictChanges = {}
        for of in range(size):
            dictChanges[(sec, offset+of)] = (self.data[sec][offset+of], valBytes[of])
        self.history.signalChange(self, dictChanges)

        self.data[sec][offset:offset+size] = valBytes

    def setBreakpoint(self, addr, modeOctal):
        self.breakpoints[addr] = modeOctal

    def toggleBreakpoint(self, addr, modeOctal):
        if not addr in self.breakpoints:
            self.setBreakpoint(addr, modeOctal)
        else:
            # Toggle the value
            self.breakpoints[addr] ^= modeOctal
        return self.breakpoints[addr]

    def deactivateBreakpoints(self):
        # Without removing them, do not trig on breakpoint until `reactivateBreakpoints`
        # is called. Useful to temporary disable breakpoints of memory
        self.bkptActive = False

    def reactivateBreakpoints(self):
        # See `deactivateBreakpoints`
        self.bkptActive = True

    def removeBreakpoint(self, addr):
        self.breakpoints[addr] = 0

    def removeExecuteBreakpoints(self, removeList=()):
        # Remove all execution breakpoints that are in removeList
        for addr in [a for a,b in self.breakpoints.items() if b & 1 == 1 and a in removeList]:
            self.removeBreakpoint(addr)
    
    def stepBack(self, state):
        for k, val in state.items():
            sec, offset = k
            self.data[sec][offset] = val[0]


