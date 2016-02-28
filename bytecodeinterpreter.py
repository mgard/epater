from procsimulator import Simulator, Memory, Register

class BCInterpreter:

    def __init__(self, bytecode, mappingInfo):
        self.bc = bytecode
        self.dbginf = mappingInfo
        self.sim = Simulator(bytecode)
        self.reset()

    def reset(self):
        self.sim.reset()

    def setBreakpoint(self, lineno):
        pass

    def setBreakpointMem(self, addr):
        pass

    def stepforward(self):
        self.sim.nextInstr()

    def stepinto(self):
        self.sim.nextInstr()

    def stepout(self):
        pass

    def run(self):
        pass

    def getMemory(self):
        return self.sim.mem.formatMemToDisplay()

    def getRegisters(self):
        return list(r.get() for r in self.sim.regs)

