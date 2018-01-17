from struct import unpack

from settings import getSetting
from simulator import Simulator
import operator
from components import Breakpoint


class BCInterpreter:
    """
    This class is the main interface for the ARM simulator. It is responsible for initializing it and provide methods
    to access to its state or modify it. Technically, all communication between the interface and the simulator
    should go through this class.
    """

    def __init__(self, bytecode, mappingInfo, assertInfo={}, pcInitAddr=0):
        """
        Initialize the bytecode interpreter (simulator).

        :param bytecode: an bytes/bytearray object containing the bytecode to execute
        :param mappingInfo: the line/address mapping dictionnary produced by the assembler
        :param assertInfo: the assertion dictionnary produced by the assembler
        :param pcInitAddr: the address at which PC should start (default 0)
        """
        self.bc = bytecode
        self.addr2line = mappingInfo
        self.assertInfo = assertInfo
        # Useful to set line breakpoints
        self.line2addr = {}
        for addr,lines in mappingInfo.items():
            for line in lines:
                self.line2addr[line] = addr
        self.lineBreakpoints = []
        self.sim = Simulator(bytecode, self.assertInfo, self.addr2line, pcInitAddr)
        self.reset()

    def reset(self):
        """
        Reset the state of the simulator (as an ARM reset exception). Memory content is preserved.
        """
        self.sim.reset()

    def getBreakpointInstr(self, diff=False):
        """
        Return all the breakpoints defined in the simulator.

        :param diff: if True, returns only the changes since the last call to this function.
        """
        if diff and hasattr(self, '_oldLineBreakpoints'):
            ret = list(set(self.lineBreakpoints) ^ self._oldLineBreakpoints)
        else:
            ret = self.lineBreakpoints

        self._oldLineBreakpoints = set(self.lineBreakpoints)
        return ret

    def setBreakpointInstr(self, listLineNumbers):
        """
        Set breakpoints at the line numbers specified.

        :param listLineNumbers: an iterable
        """
        # First, we remove all execution breakpoints
        self.sim.mem.removeExecuteBreakpoints(removeList=[self.line2addr[b] for b in self.lineBreakpoints])

        # Now we add all breakpoint
        # The easy case is when the line is directly mapped to a memory address (e.g. it is an instruction)
        # When it's not, we have to find the closest next line which is mapped
        # If there is no such line (we are asked to put a breakpoint after the last line of code) then no breakpoint is set
        self.lineBreakpoints = []
        for lineno in listLineNumbers:
            if lineno in self.line2addr:
                self.sim.mem.setBreakpoint(self.line2addr[lineno], 1)
                nextLine = lineno + 1
                while nextLine in self.line2addr and self.line2addr[nextLine] == self.line2addr[lineno]:
                    nextLine += 1
                if nextLine-1 not in self.lineBreakpoints:
                    self.lineBreakpoints.append(nextLine-1)

    def getBreakpointsMem(self):
        """
        Returns the breakpoints currently set in memory.
        This is returned as a dictionary with 4 keys: 'r', 'w' 'rw', and 'e' (read, write, read/write and execute)
        Each of these keys is associated to a list containing all the breakpoints of this type
        """
        return {
            'r': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 4],
            'w': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 2],
            'rw': [k for k,v in self.sim.mem.breakpoints.items() if (v & 6) == 6],
            'e': [k for k,v in self.sim.mem.breakpoints.items() if bool(v & 1)],
        }

    def setBreakpointMem(self, addr, mode):
        """
        Add a memory breakpoint.

        :param addr: Address to set the breakpoint
        :param mode: breakpoint type. Either one of 'r' | 'w' | 'rw' | 'e' or an empty string. The empty string
        removes any breakpoint at this address
        """
        # Mode = 'r' | 'w' | 'rw' | 'e' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode) + 1*('e' in mode)
        self.sim.mem.setBreakpoint(addr, modeOctal)


    def toggleBreakpointMem(self, addr, mode):
        """
        Toggle a breakpoint in memory.

        :param addr: Address to toggle the breakpoint
        :param mode: breakpoint mode (see setBreakpointMem)
        """
        # Mode = 'r' | 'w' | 'rw' | 'e' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode) + 1*('e' in mode)
        bkptInfo = self.sim.mem.toggleBreakpoint(addr, modeOctal)
        if 'e' in mode:
            addrprod4 = (addr // 4) * 4
            if addrprod4 in self.addr2line:
                if bkptInfo & 1:        # Add line breakpoint
                    self.lineBreakpoints.append(self.addr2line[addrprod4][-1])
                else:                   # Remove line breakpoint
                    try:
                        self.lineBreakpoints.remove(self.addr2line[addrprod4][-1])
                    except ValueError:
                        # Not sure how we can reach this, but just in case, it is not a huge problem so we do not want to crash
                        pass


    def setBreakpointRegister(self, bank, reg, mode):
        """
        Set a breakpoint on register access

        :param bank: bank of the register (can be either "user", "FIQ", "IRQ" or "SVC")
        :param reg: register on which to set the breakpoint, should be an integer between 0 and 15
        :param mode: breakpoint mode ('r', 'w', 'rw'). Passing an empty string removes the breakpoint.
        """
        # Mode = 'r' | 'w' | 'rw' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode)
        bank = "User" if bank == "user" else bank.upper()
        self.sim.regs.getRegisterFromBank(bank, reg).breakpoint = modeOctal

    def setBreakpointFlag(self, flag, mode):
        """
        Set a breakpoint on flag access

        :param flag: flag on which to set the breakpoint
        :param mode: breakpoint mode ('r', 'w', 'rw'). Passing an empty string removes the breakpoint.
        """
        # Mode = 'r' | 'w' | 'rw' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode)
        self.sim.flags.breakpoints[flag.upper()] = modeOctal

    def setInterrupt(self, type, clearinterrupt, ncyclesbefore=0, ncyclesperiod=0, begincountat=0):
        """
        Set an interrupt.

        :param type: either "FIQ" or "IRQ"
        :param clearinterrupt: if set to True, clear (remove) the interrupt
        :param ncyclesbefore: number of cycles to wait before the first interrupt
        :param ncyclesperiod: number of cycles between two interrupts
        :param begincountat: begincountat gives the t=0 as a cycle number.
                                If it is 0, then the first interrupt will happen at time t=ncyclesbefore
                                If it is > 0, then it will be at t = ncyclesbefore + begincountat
                                If < 0, then the begin cycle is set at the current cycle
        """
        self.sim.interruptActive = not clearinterrupt
        self.sim.interruptParams['b'] = ncyclesbefore
        self.sim.interruptParams['a'] = ncyclesperiod
        self.sim.interruptParams['t0'] = begincountat if begincountat >= 0 else self.sim.sysHandle.countCycles
        self.sim.interruptParams['type'] = type.upper()
        self.sim.lastInterruptCycle = -1


    @property
    def shouldStop(self):
        """
        Boolean property telling if the current task is done
        """
        return self.sim.isStepDone()

    @property
    def currentBreakpoint(self):
        """
        Returns a list of namedTuple with the fields
        'source' = 'register' | 'memory' | 'flag' | 'assert' | 'pc'
        'mode' = integer (same interpretation as Unix permissions)
                          if source='memory' then mode can also be 8 : it means that we're trying to access an uninitialized memory address
        'infos' = supplemental information (register index if source='register', flag name if source='flag', address if source='memory')
                      if source='assert', then infos is a tuple (line (integer), description (string))
        If no breakpoint has been trigged in the last instruction, then return None
        """
        return self.sim.sysHandle.breakpointInfo if self.sim.sysHandle.breakpointTrigged else None

    def execute(self, mode="into"):
        """
        Run the simulator in a given mode.
        :param stepMode: can be "into" | "forward" | "out" | "run"
        """
        self.sim.setStepCondition(mode)
        self.sim.loop()

    def step(self, stepMode=None):
        """
        Run the simulator in a given mode.
        :param stepMode: can be "into" | "forward" | "out" | "run" or None, which means to
                keep the current mode, whatever it is
        """
        if stepMode is not None:
            self.sim.setStepCondition(stepMode)
        self.sim.loop()

    def stepBack(self, count=1):
        """
        Step back the simulation
        :param count: number of cycles to step back
        """
        self.sim.stepBack(count)
        self.sim.fetchAndDecode()

    def getMemory(self, addr, returnHexaStr=True):
        """
        Get the value of an address in memory.

        :param addr: the address to access. If it does not exist or it is not mapped, then "--" is returned
        :param returnHexaStr: if True, return a string containing the hexadecimal representation of the value
                                instead of the value itself
        :return: byte or string, depending on returnHexaStr
        """
        val = self.sim.mem.get(addr, 1, mayTriggerBkpt=False)
        if val is None:
            return "--"
        if returnHexaStr:
            return "{:02X}".format(unpack("B", val)[0])
        else:
            return val

    def getMemoryFormatted(self):
        """
        Return the content of the memory, serialized in a way that can be read by the UI.
        """
        sorted_mem = sorted(self.sim.mem.startAddr.items(), key=operator.itemgetter(1))
        retList = []
        data = self.sim.mem.getContext()
        for sec, start in sorted_mem:
            padding_size = start - len(retList)
            retList += ["--"] * padding_size
            retList += ["{:02X}".format(d) for d in data[sec]]
        return retList

    def setMemory(self, addr, val):
        """
        Set the value of a given address in memory.

        :param addr: the address to write. If it does not exist or it is not mapped, then nothing is performed and
                        this function simply returns.
        :param val: the value to write, as a bytearray of one element.
        """
        # if addr is not initialized, then do nothing
        # val is a bytearray of one element (1 byte)
        if self.sim.mem._getRelativeAddr(addr, 1) is None:
            return
        self.sim.mem.set(addr, val[0], 1)
        pc = self.sim.regs[15].get(mayTriggerBkpt=False)
        pc -= 8 if getSetting("PCbehavior") == "+8" else 0
        if 0 <= addr - pc < 4:
            # We decode the instruction again
            self.sim.fetchAndDecode()

    def getCurrentInfos(self):
        """
        Return the current simulator state, with information relevant to the UI. The value is returned as :
        [["highlightread", ["r3", "SVC_r12", "z", "sz"]], ["highlightwrite", ["r1", "MEM_adresseHexa"]], ["nextline", 42], ["disassembly", ""]]

        See the interface for an explanation of this syntax
        """
        # We must clone each element so we do not change the internals of the simulator
        s = tuple(x[:] for x in self.sim.disassemblyInfo)

        # Convert nextline from addr to line number
        idx = [i for i, x in enumerate(s) if x[0] == "nextline"]
        try:
            s[idx[0]][1] = self.addr2line[s[idx[0]][1]][-1]
        except IndexError:
            s = [x for i, x in enumerate(s) if x[0] != "nextline"]

        return s

    def getRegisters(self):
        """
        Get the value of all the registers for all banks.
        """
        return self.sim.regs.getAllRegisters()

    def setRegisters(self, regsDict):
        """
        Set a variable number of registers at once.

        :param regsDict: a dictionnary containing a mapping between register (an integer) and a value
        """
        for r,v in regsDict.items():
            self.sim.regs[r] = v
        # Changing the registers may change some infos in the prediction (for instance, memory cells affected by a mem access)
        self.sim.decodeInstr()

    def getFlagsFormatted(self):
        result = []
        flags = self.getFlags()
        result.extend(tuple({k.lower(): "{}".format(v) for k,v in flags.items()}.items()))
        if 'SN' not in flags:
            flags = ("sn", "sz", "sc", "sv", "si", "sf")
            result.extend([("disable", f) for f in flags])
        return result

    def getFlags(self):
        """
        Return a dictionnary of the flags; if the current mode has a SPSR, then this method also returns
        its flags, with their name prepended with 'S', in the same dictionnary
        """
        cpsr = self.sim.regs.CPSR
        try:
            spsr = self.sim.regs.SPSR
            flags = self.__parseFlags(cpsr=cpsr, spsr=spsr)
        except Breakpoint:
            # Currently in user mode
            flags = self.__parseFlags(cpsr=cpsr)
        return flags

    def setFlags(self, flagsDict):
        """
        Set the flags in CPSR and the current SPSR (if there is such register)

        :param flagsDict: a dictionnary with flag names as keys and booleans as values. To set the SPSR flags,
                        the keys to use are the same as the CPSR, but prepended with a 'S' (e.g. use 'SC' to reference
                        carry flag in the current SPSR)
        """
        hasSPSR = self.sim.regs.getSPSR() is not None
        for f,v in flagsDict.items():
            if hasSPSR and len(f) == 2:
                f = f[1]
                self.sim.regs.getSPSR().setFlag(f.upper(), int(v), mayTriggerBkpt=False)
            elif len(f) == 1:
                self.sim.flags.setFlag(f.upper(), int(v), mayTriggerBkpt=False)
        # Changing the flags may change the decision to execute or not the next instruction, we update it
        self.sim.decodeInstr()

    def getProcessorMode(self):
        """
        Return the current processor mode (user, FIQ, IRQ, SVC)
        """
        return self.sim.regs.mode

    def getCycleCount(self):
        """
        Return the current number of cycles (the number of instructions executed since the beginning of the simulation)
        """
        return self.sim.history.cyclesCount

    def getChangesFormatted(self):
        """
        Return all the changes since the last checkpoint, serialized in a way that can be read by the UI.
        """
        result = []
        changes = self.sim.history.getDiffFromCheckpoint()

        registers_changes =  changes.get(self.sim.regs.__class__)
        for reg, value in registers_changes.items():
            if reg[0] == 'User':
                if reg[1] == 'CPSR':
                    result.extend(tuple({k.lower(): "{}".format(v)
                                         for k,v in self.__parseFlags(cpsr=value[1]).items()}.items()))
                else:
                    result.append(['r{}'.format(reg[1]), '{:08x}'.format(value[1])])
            else:
                result.append(['{}_r{}'.format(reg[0], reg[1]), '{:08x}'.format(value[1])])

        memory_changes = changes.get(self.sim.mem.__class__)
        result.append(["mempartial", [[k[1], "{:02x}".format(v[1]).upper()] for k, v in memory_changes.items()]])

        return result


    def getChanges(self):
        return self.sim.history.getDiffFromCheckpoint()

    def getCurrentLine(self):
        """
        Return the number of the line currently accessed.
        """
        self.sim.regs.deactivateBreakpoints()
        pc = self.sim.regs[15]
        self.sim.regs.reactivateBreakpoints()
        pc -= 8 if getSetting("PCbehavior") == "+8" else 0
        assert pc in self.addr2line, "Line outside of linked memory!"
        assert len(self.addr2line[pc]) > 0, "Line outside of linked memory!"
        return self.addr2line[pc][-1]

    def getCurrentInstructionAddress(self):
        """
        Return the address of the instruction being executed
        """
        self.sim.regs.deactivateBreakpoints()
        pc = self.sim.regs[15]
        self.sim.regs.reactivateBreakpoints()
        pc -= 8 if getSetting("PCbehavior") == "+8" else 0
        return pc

    def __parseFlags(self, cpsr=None, spsr=None):
        d = {}
        if cpsr:
            d.update({flag: bool((cpsr >> self.sim.regs.flag2index[flag]) & 0x1) for flag in self.sim.regs.flag2index.keys()})
        if spsr:
            d.update({"S{}".format(flag): bool((spsr >> self.sim.regs.flag2index[flag]) & 0x1)
                      for flag in self.sim.regs.flag2index.keys()})
        return d


