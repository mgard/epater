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
        return list(r.get() for r in self.sim.regs)

    def getCurrentLine(self):
        pc = self.sim.regs[15].get()
        assert pc in self.dbginf, "Line outside of linked memory!"
        return self.dbginf[pc][-1]

    def getProcessorState(self):
        r = []

        return r

