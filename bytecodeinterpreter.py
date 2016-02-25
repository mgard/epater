from procsimulator import Simulator, Memory, Register

class BCInterpreter:

    def __init__(self, bytecode, mappingInfo):
        self.bc = bytecode
        self.dbginf = mappingInfo
        self.sim = Simulator()

    def reset(self):
        pass

    def setBreakpoint(self, lineno):
        pass

    def setBreakpointMem(self, addr):
        pass

    def stepforward(self):
        pass

    def stepinto(self):
        pass

    def stepout(self):
        pass

    def run(self):
        pass

