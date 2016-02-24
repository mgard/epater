

class BCInterpreter:

    def __init__(self, bytecode):
        self.bc, self.dbginf, self.sim = None, None, None
        self.setBytecode(bytecode)

    def setBytecode(self, bytecode):
        self.bc = bytecode

    def setLineMapping(self, debuginfo):
        self.dbginf = debuginfo

    def setSimulator(self, simulator):
        self.sim = simulator

    def reset(self):
        pass

    def setBreakpoint(self, lineno):
        pass

    def stepforward(self):
        pass

    def stepinto(self):
        pass

    def stepreturn(self):
        pass

    def run(self):
        pass

