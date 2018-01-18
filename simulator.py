import operator
import struct
import time

from enum import Enum
from collections import defaultdict, namedtuple, deque

from settings import getSetting
from components import Registers, Memory, Breakpoint
from history import History
from simulatorOps.utils import checkMask
from simulatorOps import *

class Simulator:
    """
    Main simulator class.
    None of its method should be called directly by the UI, 
    everything should pass through bytecodeinterpreter class.
    """
    PC = 15     # Helpful shorthand to get a reference on PC

    def __init__(self, memorycontent, assertionTriggers, addr2line, pcInitValue=0):
        # Parameters
        self.pcoffset = 8 if getSetting("PCbehavior") == "+8" else 0
        self.PCSpecialBehavior = getSetting("PCspecialbehavior")
        self.allowSwitchModeInUserMode = getSetting("allowuserswitchmode")
        self.maxit = getSetting("runmaxit")

        # Initialize history
        self.history = History()

        # Initialize components
        self.mem = Memory(self.history, memorycontent)
        self.regs = Registers(self.history)
        self.pcInitVal = pcInitValue

        # Initialize decoders
        self.decoders = {'BranchOp': BranchOp(), 'DataOp': DataOp(), 
                            'MemOp': MemOp(), 'MultipleMemOp': MultipleMemOp(),
                            'HalfSignedMemOp': HalfSignedMemOp(),
                            'PSROp': PSROp(),
                            'MulOp': MulOp(), 'MulLongOp': MulLongOp(), 
                            'SoftInterruptOp': SoftInterruptOp(), 'NopOp': NopOp()}
        self.decoderCache = {}

        # Initialize assertion structures
        self.assertionCkpts = set(assertionTriggers.keys())
        self.assertionData = assertionTriggers
        self.assertionWhenReturn = set()
        self.callStack = []
        self.addr2line = addr2line

        # Initialize interrupt structures
        self.interruptActive = False
        # Interrupt trigged at each a*(t-t0) + b cycles
        self.interruptParams = {'b': 0, 'a': 0, 't0': 0, 'type': "FIQ"}       
        self.lastInterruptCycle = -1

        self.stepMode = None
        self.stepCondition = 0
        # Used to stop the simulator after n iterations in run mode
        self.runIteration = 0
        self.history.clear()

    def reset(self):
        self.history.clear()
        self.regs.banks['User'][15].val = self.pcInitVal + self.pcoffset
        self.fetchAndDecode()
        self.explainInstruction()

    def getContext(self):
        context = {"regs": self.regs.getContext(),
                    "mem": self.mem.getContext()}
        return context


    def setStepCondition(self, stepMode):
        assert stepMode in ("into", "out", "forward", "run")
        self.stepMode = stepMode
        self.stepCondition = 1
        self.runIteration = self.history.cyclesCount

    def isStepDone(self):
        maxCyclesReached = self.history.cyclesCount - self.runIteration >= self.maxit
        if self.stepMode == "forward":
            if self.stepCondition == 2:
                # The instruction was a function call
                # Now the step forward becomes a step out
                self.stepMode = "out"
                self.stepCondition = 1
                return False
            else:
                return maxCyclesReached
        if self.stepMode == "out":
            return self.stepCondition == 0 or maxCyclesReached
        if self.stepMode == "run":
            return maxCyclesReached

        # We are doing a step into, we always stop
        return True

    def loop(self):
        """
        Loop until the stopping criterion is met. Returns the aggregated list
        of changes since the beginning of the simulation loop.
        Stopping criterion can be set using `setStepCondition`.
        """
        a = time.time()
        self.history.setCheckpoint()
        self.nextInstr()                # We always execute at least one instruction
        while not self.isStepDone():    # We repeat until the stopping criterion is met
            self.nextInstr()
        self.explainInstruction()       # We only have to explain the last instruction executed before we stop
        print("TIME TAKEN ", time.time() - a)
        return self.history.getDiffFromCheckpoint()

    def stepBack(self, count=1):
        for c in range(count):
            self.history.stepBack()

    def fetchAndDecode(self):
        # Check if PC is valid (multiple of 4)
        if (self.regs[15] - self.pcoffset) % 4 != 0:
            raise Breakpoint("register", 8, 15, "Erreur : la valeur de PC ({}) est invalide (ce doit être un multiple de 4)!".format(hex(self.regs[15].get())))
        # Retrieve instruction from memory
        self.fetchedInstr = bytes(self.mem.get(self.regs[15] - self.pcoffset, execMode=True))
        self.bytecodeToInstr()


    def bytecodeToInstr(self):
        # Assumes that the instruction to decode is in self.fetchedInstr
        instrInt = struct.unpack("<I", self.fetchedInstr)[0]
        if instrInt in self.decoderCache:
            self.currentInstr = self.decoderCache[instrInt][0]
            self.currentInstr.setBytecode(instrInt)
            self.currentInstr.restoreState(self.decoderCache[instrInt][1])
            return

        # Select the right data type to handle the decoding
        # We have to be extra careful here and go from the specific to
        # the general. For instance, dataOp check should NOT be the first, since
        # we can only check for 0's at positions 27-26, but this characteristic is
        # shared with many other instruction types
        if checkMask(instrInt, (19, 24), (27, 26, 23, 20)):       # MRS or MSR
            # This one is tricky
            # The signature looks like a data processing operation, BUT
            # it sets the "opcode" to an operation beginning with 10**, 
            # and the only operations that match this are TST, TEQ, CMP and CMN
            # It is said that for these ops, the S flag MUST be set to 1
            # With MSR and MRS, the bit representing the S flag is always 0, 
            # so we can differentiate these instructions...
            self.currentInstr = self.decoders['PSROp']
        elif checkMask(instrInt, (7, 4, 24), (27, 26, 25, 23, 21, 20, 11, 10, 9, 8, 6, 5)):
            # Swap
            # This one _must_ be before Data processing check, since it overlaps
            self.currentInstr = self.decoders['SwapOp']
        elif checkMask(instrInt, (7, 4), (27, 26, 25)):
            # Half/signed data transfer
            # This one _must_ be before Data processing check, since it overlaps,
            # but also _must_ be _after_ Swap check, because swap is a specialized case of this one
            self.currentInstr = self.decoders['HalfSignedMemOp']
        elif checkMask(instrInt, (24, 21, 4) + tuple(range(8, 20)), (27, 26, 25, 23, 22, 20, 7, 6, 5)):
            # BX
            # This one _must_ be before Data processing check, since it overlaps
            self.currentInstr = self.decoders['BranchOp']
        elif checkMask(instrInt, (7, 4), tuple(range(22, 28)) + (5, 6)):
            # MUL or MLA
            # This one _must_ be before Data processing check, since it overlaps
            self.currentInstr = self.decoders['MulOp']
        elif checkMask(instrInt, (7, 4, 23), tuple(range(24, 28)) + (5, 6)):
            # UMULL, SMULL, UMLAL or SMLAL
            # This one _must_ be before Data processing check, since it overlaps
            self.currentInstr = self.decoders['MulLongOp']
        elif checkMask(instrInt, (25, 24, 21), (27, 26, 23, 22, 20, 19, 18, 17, 16)):
            # NOP
            # This one _must_ be before Data processing check, since it overlaps
            self.currentInstr = self.decoders['NopOp']
        elif checkMask(instrInt, (), (27, 26)):
            # Data processing
            self.currentInstr = self.decoders['DataOp']
        elif checkMask(instrInt, (26, 25), (4, 27)) or checkMask(instrInt, (26,), (25, 27)):
            # Single data transfer
            self.currentInstr = self.decoders['MemOp']
        elif checkMask(instrInt, (27, 25), (26,)):
            # Branch
            self.currentInstr = self.decoders['BranchOp']
        elif checkMask(instrInt, (27,), (26, 25)):
            # Block data transfer
            self.currentInstr = self.decoders['MultipleMemOp']
        elif checkMask(instrInt, (24, 25, 26, 27), ()):
            # Software interrupt
            self.currentInstr = self.decoders['SoftInterruptOp']
        else:
            # Undefined instruction
            self.currentInstr = None

        if self.currentInstr is not None:
            self.currentInstr.setBytecode(instrInt)
            self.currentInstr.decode()
            # Once decoded, we add the instruction to the cache
            self.decoderCache[instrInt] = (self.currentInstr, self.currentInstr.saveState())
            if len(self.decoderCache) > 2000:
                # Fail-safe, we should never get there with programs < 2000 lines, but just in case,
                # we do not want to bust the RAM with our cache
                self.decoderCache = {}

    def explainInstruction(self):
        disassembly, description = self.currentInstr.explain(self)
        dis = '<div id="disassembly_instruction">{}</div>\n<div id="disassembly_description">{}</div>\n'.format(disassembly, description)

        if self.currentInstr.nextAddressToExecute != -1:
            self.disassemblyInfo = (["highlightread", list(self.currentInstr.affectedRegs[0] | self.currentInstr.affectedMem[0])], 
                                    ["highlightwrite", list(self.currentInstr.affectedRegs[1] | self.currentInstr.affectedMem[1])], 
                                    ["nextline", self.currentInstr.nextAddressToExecute], 
                                    ["disassembly", dis])
        else:
            self.disassemblyInfo = (["highlightread", list(self.currentInstr.affectedRegs[0] | self.currentInstr.affectedMem[0])], 
                                    ["highlightwrite", list(self.currentInstr.affectedRegs[1] | self.currentInstr.affectedMem[1])],
                                    ["disassembly", dis])

    def execAssert(self, assertionsList, mode):
        # TODO
        pass

    def nextInstr(self):
        # One more cycle to do!
        self.history.newCycle()

        if self.currentInstr is None:
            # The current instruction has not be retrieved or decoded (because it was an illegal access)
            return

        keeppc = self.regs[15] - self.pcoffset

        currentCallStackLen = len(self.callStack)

        try:
            self.currentInstr.execute(self)
        except Breakpoint as bp:
            # We hit a breakpoint, or there is an execution error
            if bp.mode == 8:
                # Error! We report it to the UI
                pass    # TODO
            self.stepMode = None
            return

        if self.currentInstr.pcmodified:
            # We don't want this to be logged in the history since this
            # was just a transitioning value
            self.regs.setRegister("User", 15, self.regs[15] + self.pcoffset, logToHistory=False) 
        else:
            self.regs[15] += 4       # PC = PC + 4

        newpc = self.regs[15] - self.pcoffset

        # TODO : Make assertion works with the new simulator
        if keeppc in self.assertionCkpts and not self.currentInstr.pcmodified:
            # We check if we've hit an post-assertion checkpoint
            self.execAssert(self.assertionData[keeppc], 'AFTER')
        elif currentCallStackLen > len(self.callStack):
            # We have branched out of a function
            # If an assertion was following a BL and we exited a function, we want to execute it now!
            if len(self.callStack) in self.assertionWhenReturn and (newpc-4) in self.assertionCkpts:
                self.execAssert(self.assertionData[newpc-4], 'AFTER')
                self.assertionWhenReturn.remove(len(self.callStack))
        elif currentCallStackLen < len(self.callStack):
            # We have branched in a function
            # We want to remember that we want to assert something when we return
            if keeppc in self.assertionCkpts:
                self.assertionWhenReturn.add(currentCallStackLen)

        if newpc in self.assertionCkpts:
            # We check if we've hit an pre-assertion checkpoint (for the next instruction)
            self.execAssert(self.assertionData[newpc], 'BEFORE')

        # We look for interrupts
        # The current instruction is always finished before the interrupt
        # TODO Handle special cases for LDR and STR multiples
        if self.interruptActive and (self.lastInterruptCycle == -1 and self.history.cyclesCount - self.interruptParams['b'] >= self.interruptParams['t0'] or
                                        self.lastInterruptCycle >= 0 and self.history.cyclesCount - self.lastInterruptCycle >= self.interruptParams['a']):
            if (self.interruptParams['type'] == "FIQ" and not self.regs.FIQ or
                    self.interruptParams['type'] == "IRQ" and not self.regs.IRQ):        # Is the interrupt masked?
                # Interruption!
                # We enter it (the entry point is 0x18 for IRQ and 0x1C for FIQ)
                savedCPSR = self.regs.CPSR                                  # Saving CPSR before changing processor mode
                self.regs.mode = self.interruptParams['type']               # Set the register bank and processor mode
                self.regs.SPSR = savedCPSR                                  # Save the CPSR in the current SPSR
                if self.interruptParams['type'][0] == "FIQ":
                    self.regs.FIQ = True                                    # Disable interrupts
                else:
                    self.regs.IRQ = True
                self.regs[14] = self.regs[15] - 4                           # Save PC in LR (on the FIQ or IRQ bank)
                self.regs[15] = self.pcoffset + (0x18 if self.interruptParams['type'] == "IRQ" else 0x1C)      # Set PC to enter the interrupt
                self.lastInterruptCycle = self.history.cyclesCount

        # We fetch and decode the next instruction
        self.fetchAndDecode()

        # Question : if we hit a breakpoint for the _next_ instruction, should we enter the interrupt anyway?
        # Did we hit a breakpoint?
        # A breakpoint always stop the simulator

