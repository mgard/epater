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
from simulatorOps.abstractOp import ExecutionException

class MultipleErrors(Exception):
    """
    This exception class is used to store multiple execution errors. It is useful if there
    are multiple errors in one instruction. Also, this class can be iterated to treat each error individually.
    """
    def __init__(self, error = None, info = None, line = None):
        """
        Initialize a empty class if error and info are None.
        Otherwise, initialize the class with the corresponding parameters.

        :param error: a str containing the error type
        :param info: a str containing information on the error
        :param line: the line number when the error occurs (default None)
        """
        if error and info:
            self.content = [(error, info, line)]
        else:
            self.content = []
        self.idx = 0

    def __bool__(self):
        return len(self.content) != 0

    def __iter__(self):
        return self

    def __next__(self):
        try:
            retval = self.content[self.idx]
        except IndexError:
            self.idx = 0
            raise StopIteration()
        self.idx += 1
        return retval

    def append(self, error, info, line = None):
        self.content.append((error, info, line))

    def clear(self):
        self.idx = 0
        self.content = []


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
        self.bkptLastFetch = None
        self.deactivatedBkpts = []

        # Initialize history
        self.history = History()

        # Initialize components
        self.mem = Memory(self.history, memorycontent)
        self.regs = Registers(self.history)
        self.pcInitVal = pcInitValue

        # Initialize decoders
        self.decoders = {'BranchOp': BranchOp(), 'DataOp': DataOp(), 
                            'MemOp': MemOp(), 'MultipleMemOp': MultipleMemOp(),
                            'HalfSignedMemOp': HalfSignedMemOp(), 'SwapOp': SwapOp(),
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

        # Initialize execution errors buffer
        self.errorsPending = MultipleErrors()

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
        self.history.setCheckpoint()
        for decoder in self.decoders.values():
            decoder.resetExecCounters()
        self.nextInstr()                # We always execute at least one instruction
        while not self.isStepDone():    # We repeat until the stopping criterion is met
            self.nextInstr()
        self.explainInstruction()       # We only have to explain the last instruction executed before we stop

    def stepBack(self, count=1):
        for c in range(count):
            self.history.stepBack()
        self.fetchAndDecode()

    def executionStats(self):
        """
        Return a dictionnary with the number of times each instruction type was executed
        in the last execution run.
        The types are:
        - "data" (includes all arithmetic and logic operations except multiply)
        - "mem" (includes all _single_ memory accesses including byte, half or word access and swap)
        - "multiplemem" (all _multiple_ memory accesses: LDM, STM, POP, and PUSH)
        - "branch" (all branches, B/BL/BX alike)
        - "multiply" (multiply and multiply long operations)
        - "softinterrupt" (self explanatory)
        - "psr" (CPSR/SPRS <-> register transfers)
        - "nop" (NOP instructions)

        These keys are associated to a 2-integers tuple. The first value is the number of times
        this kind of instruction was executed, the second the number of times if _would_ have been
        executed except for the condition field (e.g. the condition was not met).
        """
        memExec = self.decoders['MemOp'].execCounters
        halfMemExec = self.decoders['HalfSignedMemOp'].execCounters
        swapExec = self.decoders['SwapOp'].execCounters
        multiplyExec = self.decoders['MulOp'].execCounters
        multiplyLongExec = self.decoders['MulLongOp'].execCounters

        return {"data": self.decoders['DataOp'].execCounters,
                "mem": (memExec[0] + halfMemExec[0] + swapExec[0], memExec[1] + halfMemExec[1] + swapExec[1]),
                "multiplemem": self.decoders['MultipleMemOp'].execCounters,
                "branch": self.decoders['BranchOp'].execCounters,
                "multiply": (multiplyExec[0] + multiplyLongExec[0], multiplyExec[1] + multiplyLongExec[1]),
                "softinterrupt": self.decoders['SoftInterruptOp'].execCounters,
                "psr": self.decoders['PSROp'].execCounters,
                "nop": self.decoders['NopOp'].execCounters}

    def fetchAndDecode(self, forceExplain=False):
        # Check if PC is valid (multiple of 4)
        if (self.regs[15] - self.pcoffset) % 4 != 0:
            self.fetchedInstr = None
            self.errorsPending.append('register', "Erreur : la valeur de PC ({}) est invalide (ce doit être un multiple de 4)!".format(hex(self.regs[15])))
        else:
            try:
                # Retrieve instruction from memory
                self.fetchedInstr = bytes(self.mem.get(self.regs[15] - self.pcoffset, execMode=True))
            except Breakpoint as bp:
                # We hit a breakpoint, or there is an execution error
                if bp.mode == 8:
                    # Execution error
                    self.errorsPending.append(bp.cmp, bp.desc)
                    # There is no instruction to this address
                    self.fetchedInstr = None
                else:
                    # Get memory instruction again, without trigger breakpoint
                    self.fetchedInstr = bytes(self.mem.get(self.regs[15] - self.pcoffset, mayTriggerBkpt=False))
                    self.bkptLastFetch = bp

        self.bytecodeToInstr()
        if forceExplain or self.isStepDone():
            self.explainInstruction()


    def bytecodeToInstr(self):
        """
        Decode an instruction from its bytecode representation.

        See ARM Instruction set documentation for more information (Fig 4.1,
        and also Sec. A5.1 of ARM-v7 Architecture Reference Manual).
        We use the following decoding scheme, designed to ensure that avoid any
        instruction representation clash and also to reduce the number of
        conditions having to be checked in total. Each number inside [ ]
        represents a bit position. The usual binary ops symbols apply.

        Note that NOP was backported from ARMv7, and that ARMv4 coprocessor
        instructions are not supported. Also, we do not explicitely check for
        undefined instructions (in the ARM terminology, they are more
        _unpredictable_ than undefined).

        Decoded instructions are also cached to improve performance.

       Bytecode input 
         (4 bytes)
             |
             |
             v
        [~26 & ~27]---------------------------------------------------------v
             |                                                              |
             | FALSE                                                        | TRUE
             |                                                              |
             v                                                              v
           [26 ]--------------------------------v                           |
             |                                  |                           |
             | FALSE                            | TRUE                      |
             |                                  |                           |
             v                                  v                           v 
           [25 ]----------------v             [27 ]-------------v           |
             |                  |               |               |           |
             | FALSE            | TRUE          | FALSE         | TRUE      |
             |                  |               |               |           |
             v                  v               v               v           v
         LDM / STM          Branch (B)      LDR / STR       SWI / SVC       |
                                         (also undefined                    |
                                             if [4])                        |
             v--------------------------------------------------------------<
             |
             v
       [4 & 7 & ~25]--------------------------------------------v
             |                                                  |
             | FALSE                                            | TRUE
             |                                                  |
             v                                                  v
      [~20 & ~23 & 24]----------v                            [5 | 6]--------v
             |                  |                               |           | TRUE 
             | FALSE            | TRUE                          | FALSE     v 
             |                  |                               |       LDRH/SH/SB
             v                  v                               v           
          DATA OP           [18 & 21]-----------v             [24 ]---------v
      (MOV, ADD, etc.)          |               |               |           | TRUE
                                | FALSE         | TRUE          | FALSE     v
                                |               |               |          SWP
                                v               v               v
             v----------------[19 ]            BX             [23 ]---------v
             |                  |                               |           | TRUE
             | TRUE             | FALSE                         | FALSE     v
             |                  |                               |        Multiply
             v                  v                               v          long
         MSR / MRS             NOP                           Multiply
        """
        if not self.fetchedInstr:
            # Undefined instruction
            self.currentInstr = None
            return
        # Assumes that the instruction to decode is in self.fetchedInstr
        instrInt = struct.unpack("<I", self.fetchedInstr)[0]

        if instrInt in self.decoderCache:
            self.currentInstr = self.decoderCache[instrInt][0]
            self.currentInstr.setBytecode(instrInt)
            self.currentInstr.restoreState(self.decoderCache[instrInt][1])
            return

        if not (instrInt >> 26 & 3):
            if instrInt >> 4 & 9 == 9 and not (instrInt >> 25 & 1):
                if instrInt >> 5 & 3:
                    self.currentInstr = self.decoders['HalfSignedMemOp']
                elif instrInt >> 24 & 1:
                    self.currentInstr = self.decoders['SwapOp']
                elif instrInt >> 23 & 1:
                    self.currentInstr = self.decoders['MulLongOp']
                else:
                    self.currentInstr = self.decoders['MulOp']
            elif instrInt >> 24 & 1 and not (instrInt >> 20 & 9):
                if instrInt >> 18 & 9 == 9:
                    self.currentInstr = self.decoders['BranchOp']
                elif instrInt >> 19 & 1:
                    self.currentInstr = self.decoders['PSROp']
                else:
                    self.currentInstr = self.decoders['NopOp']
            else:
                self.currentInstr = self.decoders['DataOp']
        elif instrInt >> 26 & 1:
            if instrInt >> 27 & 1:
                self.currentInstr = self.decoders['SoftInterruptOp']
            else:   # Could also check for [4], which is an undefined space in the instruction set
                self.currentInstr = self.decoders['MemOp']
        elif instrInt >> 25 & 1:
            self.currentInstr = self.decoders['BranchOp']
        else:
            self.currentInstr = self.decoders['MultipleMemOp']

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
        if not self.currentInstr:
            # Undefined instruction
            self.disassemblyInfo = (["highlightread", []],
                                    ["highlightwrite", []],
                                    ["nextline", None],
                                    ["disassembly", "Information indisponible"])
            return

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
        for assertionInfo in assertionsList:
            assertionType = assertionInfo[0]
            if assertionType != mode:
                continue
            assertionLine = assertionInfo[1]
            assertionInfo = assertionInfo[2].split(",")

            strError = ""
            try:
                for info in assertionInfo:
                    info = info.strip()
                    target, value = info.split("=")
                    if target[0] == "R":
                        # Register
                        reg = int(target[1:])
                        val = int(value, base=0) & 0xFFFFFFFF
                        self.regs.deactivateBreakpoints()
                        valreg = self.regs[reg]
                        self.regs.reactivateBreakpoints()
                        if valreg != val:
                            strError += "Erreur : {} devrait valoir {}, mais il vaut {}\n".format(target, val, valreg)
                    elif target[:2] == "0x":
                        # Memory
                        addr = int(target, base=16)
                        val = int(value, base=0)
                        formatStruct = "<B"
                        if not 0 <= int(val) < 255:
                            val &= 0xFFFFFFFF
                            formatStruct = "<I"
                        valmem = self.mem.get(addr, mayTriggerBkpt=False, size=4 if formatStruct == "<I" else 1)
                        valmem = struct.unpack(formatStruct, valmem)[0]
                        if valmem != val:
                            strError += "Erreur : l'adresse mémoire {} devrait contenir {}, mais elle contient {}\n"\
                                .format(target, val, valmem)
                    elif len(target) == 1 and target in self.regs.flag2index:
                        # Flag
                        expectedVal = value != '0'
                        actualVal = self.regs.__getattribute__(target)
                        if actualVal != expectedVal:
                            strError += "Erreur : le drapeau {} devrait signaler {}, mais il signale {}\n"\
                                .format(target, expectedVal, actualVal)
                    else:
                        # Assert type unknown
                        strError += "Assertion inconnue!".format(target, val)

                if len(strError) > 0:
                    self.errorsPending.append("assert", strError, assertionLine)

            except Breakpoint as bp:
                assert bp.mode == 8
                self.errorsPending.append(bp.cmp, bp.desc, assertionLine)

    def nextInstr(self, forceExplain=False):
        if self.currentInstr is None:
            # The current instruction has not be retrieved or decoded (because it was an illegal access)
            # We raise the last error to explain the illegal access
            raise self.errorsPending

        # One more cycle to do!
        self.history.newCycle()
        # Clear previous errors
        self.errorsPending.clear()

        keeppc = self.regs[15] - self.pcoffset

        currentCallStackLen = len(self.callStack)

        if self.stepMode in ("out", "forward", "run"):
            if self.bkptLastFetch:
                # We hit a breakpoint on the last decoded instruction
                err = self.bkptLastFetch
                self.bkptLastFetch = None
                raise err
            try:
                self.currentInstr.execute(self)
            except Breakpoint as bp:
                # We hit a breakpoint on READ/WRITE, or there is an execution error
                # Disable raised breakpoint
                self.deactivatedBkpts.append(bp)
                self._toggleBreakpoint(bp)
                if bp.mode != 8:
                    # READ/WRITE breakpoint
                    raise bp
                # Execution error
                self.errorsPending.append(bp.cmp, bp.desc)
            except ExecutionException as err:
                self.errorsPending.append('execution', err.text, self.getCurrentLine())

        else:
            # In stepIn mode, breakpoints are temporary deactivate
            try:
                self.deactivateAllBreakpoints()
                self.currentInstr.execute(self)
            except Breakpoint as bp:
                # There is an execution error
                assert bp.mode == 8
                self.errorsPending.append(bp.cmp, bp.desc)
            except ExecutionException as err:
                self.errorsPending.append('execution', err.text, self.getCurrentLine())
            self.reactivateAllBreakpoints()

        # After instruction execution, restore all breakpoints
        for bp in self.deactivatedBkpts:
            self._toggleBreakpoint(bp)
        self.deactivatedBkpts = []

        if self.currentInstr.pcmodified:
            # We don't want this to be logged in the history since this
            # was just a transitioning value
            self.regs.setRegister("User", 15, self.regs[15] + self.pcoffset, logToHistory=False) 
        else:
            self.regs[15] += 4       # PC = PC + 4

        newpc = self.regs[15] - self.pcoffset
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
        self.fetchAndDecode(forceExplain)

        # Question : if we hit a breakpoint for the _next_ instruction, should we enter the interrupt anyway?
        # Did we hit a breakpoint?
        # A breakpoint always stop the simulator

        if self.errorsPending:
            raise self.errorsPending

    def deactivateAllBreakpoints(self):
        # Without removing them, do not trig on breakpoint until `reactivateAllBreakpoints`
        # is called. Useful to temporary disable breakpoints of Memory and Registers
        self.regs.deactivateBreakpoints()
        self.mem.deactivateBreakpoints()

    def reactivateAllBreakpoints(self):
        # See `deactivateAllBreakpoints`
        self.regs.reactivateBreakpoints()
        self.mem.reactivateBreakpoints()

    def getCurrentLine(self):
        self.regs.deactivateBreakpoints()
        pc = self.regs[15]
        self.regs.reactivateBreakpoints()
        pc -= 8 if getSetting("PCbehavior") == "+8" else 0
        if pc in self.addr2line and len(self.addr2line[pc]) > 0:
            return self.addr2line[pc][-1]
        else:
            return None

    def _toggleBreakpoint(self, bkptException):
        if bkptException.cmp == "memory":
            self.mem.toggleBreakpoint(bkptException.info, bkptException.mode)
        elif bkptException.cmp == "register":
            self.regs.toggleBreakpointOnRegister(bkptException.info[0], bkptException.info[1], bkptException.mode)
        elif bkptException.cmp == "flags":
            self.regs.toggleBreakpointOnFlag(bkptException.info, bkptException.mode)
