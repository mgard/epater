from procsimulator import Simulator, Memory, Register

class BCInterpreter:

    def __init__(self, bytecode, mappingInfo):
        self.bc = bytecode
        self.dbginf = mappingInfo
        self.sim = Simulator(bytecode)
        self.reset()

    def reset(self):
        self.sim.reset()

    def setBreakpointInstr(self, lineno):
        pass

    def setBreakpointMem(self, addr, mode):
        # Mode = 'r' | 'w' | 'rw'
        pass

    def setBreakpointRegister(self, reg, mode):
        # Mode = 'r' | 'w' | 'rw'
        pass

    @property
    def shouldStop(self):
        # TODO : add breakpoint handling
        return self.sim.isStepDone()

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
        assert pc in self.dbginf, "Line outside of linked memory!"
        return self.dbginf[pc][-1]

    def getProcessorState(self):
        r = []

        return r

