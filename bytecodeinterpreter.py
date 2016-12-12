from settings import getSetting
from procsimulator import Simulator, Memory, Register

class BCInterpreter:

    def __init__(self, bytecode, mappingInfo):
        self.bc = bytecode
        self.addr2line = mappingInfo
        # Useful to set line breakpoints
        self.line2addr = {}
        for addr,lines in mappingInfo.items():
            for line in lines:
                self.line2addr[line] = addr
        self.lineBreakpoints = []
        self.sim = Simulator(bytecode)
        self.reset()

    def reset(self):
        self.sim.reset()

    def setBreakpointInstr(self, listLineNumbers):
        # First, we remove all execution breakpoints
        self.sim.mem.removeExecuteBreakpoints([self.line2addr[b] for b in self.lineBreakpoints])

        # Now we add all breakpoint
        # The easy case is when the line is directly mapped to a memory address (e.g. it is an instruction)
        # When it's not, we have to find the closest next line which is mapped
        # If there is no such line (we are asked to put a breakpoint after the last line of code) then no breakpoint is set
        self.lineBreakpoints = []
        for lineno in listLineNumbers:
            if lineno in self.line2addr:
                self.sim.mem.setBreakpoint(self.line2addr[lineno], 1)
                self.lineBreakpoints.append(lineno)

    def getBreakpointsMem(self):
        return {
            'r': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 4],
            'w': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 2],
            'rw': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 6],
            'e': [k for k,v in self.sim.mem.breakpoints.items() if bool(v & 1)],
        }

    def setBreakpointMem(self, addr, mode):
        # Mode = 'r' | 'w' | 'rw' | 'e' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode) + 1*('e' in mode)
        self.sim.mem.setBreakpoint(addr, modeOctal)

    def toggleBreakpointMem(self, addr, mode):
        # Mode = 'r' | 'w' | 'rw' | 'e' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode) + 1*('e' in mode)
        self.sim.mem.toggleBreakpoint(addr, modeOctal)

    def setBreakpointRegister(self, reg, mode):
        # Mode = 'r' | 'w' | 'rw' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode)
        self.sim.regs[reg].breakpoint = modeOctal

    def setBreakpointFlag(self, flag, mode):
        # Mode = 'r' | 'w' | 'rw' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode)
        self.sim.flags.breakpoints[flag.upper()] = modeOctal

    def setInterrupt(self, type, clearinterrupt, ncyclesbefore=0, ncyclesperiod=0, begincountat=0):
        # type is either "FIQ" or "IRQ"
        # ncyclesbefore is the number of cycles to wait before the first interrupt
        # ncyclesperiod the number of cycles between two interrupts
        # clearinterrupt must be set to True if one wants to clear the interrupt
        # begincountat gives the t=0 as a cycle number. If it is 0, then the first interrupt will happen at time t=ncyclesbefore
        #   if it is > 0, then it will be at t = ncyclesbefore + begincountat
        #   if < 0, then the begin cycle is set at the current cycle
        self.sim.interruptActive = not clearinterrupt
        self.sim.interruptParams['b'] = ncyclesbefore
        self.sim.interruptParams['a'] = ncyclesperiod
        self.sim.interruptParams['t0'] = begincountat if begincountat >= 0 else self.sim.sysHandle.countCycles
        self.sim.interruptParams['type'] = type.upper()
        self.sim.lastInterruptCycle = -1


    @property
    def shouldStop(self):
        return self.sim.isStepDone()

    @property
    def currentBreakpoint(self):
        # Returns a namedTuple with the fields
        # 'source' = 'register' | 'memory' | ' flag'
        # 'mode' = integer (same interpretation as Unix permissions)
        #                   if source='memory' then mode can also be 8 : it means that we're trying to access an uninitialized memory address
        # 'infos' = supplemental information (register index if source='register', flag name if source='flag', address if source='memory')
        # If no breakpoint has been trigged in the last instruction, then return None
        return self.sim.sysHandle.breakpointInfo if self.sim.sysHandle.breakpointTrigged else None

    def step(self, stepMode="into"):
        # stepMode= "into" | "forward" | "out" | "run"
        if stepMode != "into":
            self.sim.setStepCondition(stepMode)
        self.sim.nextInstr()

    def stepBack(self, count=1):
        # step back 'count' times
        self.sim.stepBack(count)

    def getMemory(self):
        return self.sim.mem.serialize()

    def setMemory(self, addr, val):
        # if addr is not initialized, then do nothing
        # val is a bytearray of one element (1 byte)
        if self.sim.mem._getRelativeAddr(addr, 1) is None:
            return
        self.sim.mem.set(addr, val[0], 1)

    def getRegisters(self):
        return self.sim.regs.getAllRegisters()

    def setRegisters(self, regsDict):
        for r,v in regsDict:
            self.sim.regs[r].set(v, mayTriggerBkpt=False)

    def getFlags(self):
        # Return a dictionnary of the flags; if the current mode has a SPSR, then this method also returns
        # its flags, with their name prepended with 'S', in the same dictionnary
        d = self.sim.flags.getAllFlags()
        if self.sim.regs.getSPSR() is not None:
            d.update({"S{}".format(k): v for k,v in self.sim.regs.getSPSR().getAllFlags().items()})
        return d

    def setFlags(self, flagsDict):
        # Set the flags in CPSR and the current SPSR (if there is such register)
        # The input is a dictionnary with flag names as keys and booleans as values
        # To set the SPSR flags, the keys to use are the same as the CPSR, but prepended with a 'S'
        # (e.g. use 'SC' to reference carry flag in the current SPSR)
        hasSPSR = self.sim.regs.getSPSR() is not None
        for f,v in flagsDict.items():
            if hasSPSR and len(f) == 2:
                f = f[1]
                self.sim.regs.getSPSR().setFlag(f.upper(), int(v), mayTriggerBkpt=False)
            elif len(f) == 1:
                self.sim.flags.setFlag(f.upper(), int(v), mayTriggerBkpt=False)

    def getProcessorMode(self):
        return self.sim.flags.getMode()

    def getChanges(self):
        # Return the modified registers, memory, flags
        #
        return

    def getCurrentLine(self):
        pc = self.sim.regs[15].get(mayTriggerBkpt=False)
        pc -= 8 if getSetting("PCbehavior") == "+8" else 0
        # TODO : this assert will be a problem if we execute data...
        assert pc in self.addr2line, "Line outside of linked memory!"
        return self.addr2line[pc][-1]

    def getCurrentInstructionAddress(self):
        pc = self.sim.regs[15].get(mayTriggerBkpt=False)
        pc -= 8 if getSetting("PCbehavior") == "+8" else 0
        return pc


    def getProcessorState(self):
        r = []

        return r

