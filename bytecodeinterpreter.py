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
        self.sim = Simulator(bytecode)
        self.reset()

    def reset(self):
        self.sim.reset()

    def setBreakpointInstr(self, lineno):
        # The easy case is when the line is directly mapped to a memory address (e.g. it is an instruction)
        # When it's not, we have to find the closest next line which is mapped
        # If there is no such line (we are asked to put a breakpoint after the last line of code) then no breakpoint is set
        if lineno in self.line2addr:
            self.sim.mem.setBreakpoint(self.line2addr[lineno], 1)

    def getBreakpointsMem(self):
        return {
            'r': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 4],
            'w': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 2],
            'rw': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 6],
            'e': [k for k,v in self.sim.mem.breakpoints.items() if bool(v & 1)],
        }

    def setBreakpointMem(self, addr, mode):
        # Mode = 'r' | 'w' | 'rw' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode)
        self.sim.mem.setBreakpoint(addr, modeOctal)

    def setBreakpointRegister(self, reg, mode):
        # Mode = 'r' | 'w' | 'rw' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode)
        self.sim.regs[reg].breakpoint = modeOctal

    @property
    def shouldStop(self):
        return self.sim.isStepDone()

    @property
    def currentBreakpoint(self):
        # Returns a namedTuple with the fields
        # 'source' = 'register' | 'memory' | ' flag'
        # 'mode' = integer (same interpretation as Unix permissions)
        #                   if source='memory' then mode can also be 8 : it means that we're trying to access an uninitialized memory address
        # 'infos' = supplemental information (register index if source='register', flag name if source='flag', address if source='memory'
        # If no breakpoint has been trigged in the last instruction, then return None
        return self.sim.breakpointHandler.breakpointInfo if self.sim.breakpointHandler.breakpointTrigged else None

    def step(self, stepMode="into"):
        # stepMode= "into" | "forward" | "out"
        if stepMode != "into":
            self.sim.setStepCondition(stepMode)
        self.sim.nextInstr()

    def getMemory(self):
        return self.sim.mem.serialize()

    def getRegisters(self):
        return {r.name: r.get(mayTriggerBkpt=False) for r in self.sim.regs}

    def setRegisters(self, regsDict):
        for r,v in regsDict:
            self.sim.regs[r].set(v, mayTriggerBkpt=False)

    def getFlags(self):
        return {k: v.get(mayTriggerBkpt=False) for k,v in self.sim.flags.items()}

    def setFlags(self, flagsDict):
        for f,v in flagsDict.items():
            self.sim.flags[f.upper()].set(v, mayTriggerBkpt=False)

    def getChanges(self):
        # Return the modified registers, memory, flags
        return

    def getCurrentLine(self):
        pc = self.sim.regs[15].get()
        # TODO : this assert will be a problem if we execute data...
        assert pc in self.addr2line, "Line outside of linked memory!"
        return self.addr2line[pc][-1]

    def getProcessorState(self):
        r = []

        return r

