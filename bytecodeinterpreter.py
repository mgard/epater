from struct import unpack

from settings import getSetting
from procsimulator import Simulator, Memory, Register


class BCInterpreter:

    def __init__(self, bytecode, mappingInfo, assertInfo={}):
        self.bc = bytecode
        self.addr2line = mappingInfo
        self.assertInfo = assertInfo
        # Useful to set line breakpoints
        self.line2addr = {}
        for addr,lines in mappingInfo.items():
            for line in lines:
                self.line2addr[line] = addr
        self.lineBreakpoints = []
        self.sim = Simulator(bytecode, self.assertInfo, self.addr2line)
        self.reset()

    def reset(self):
        self.sim.reset()

    def getBreakpointInstr(self, diff=False):
        if diff and hasattr(self, '_oldLineBreakpoints'):
            ret = list(set(self.lineBreakpoints) ^ self._oldLineBreakpoints)
        else:
            ret = self.lineBreakpoints

        self._oldLineBreakpoints = set(self.lineBreakpoints)
        return ret

    def setBreakpointInstr(self, listLineNumbers):
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
                self.lineBreakpoints.append(nextLine-1)

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
        # Mode = 'r' | 'w' | 'rw' | '' (passing an empty string removes the breakpoint)
        modeOctal = 4*('r' in mode) + 2*('w' in mode)
        bank = "User" if bank == "user" else bank.upper()
        self.sim.regs.getRegisterFromBank(bank, reg).breakpoint = modeOctal

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
        # 'source' = 'register' | 'memory' | 'flag' | 'assert'
        # 'mode' = integer (same interpretation as Unix permissions)
        #                   if source='memory' then mode can also be 8 : it means that we're trying to access an uninitialized memory address
        # 'infos' = supplemental information (register index if source='register', flag name if source='flag', address if source='memory')
        #               if source='assert', then infos is a tuple (line (integer), description (string))
        # If no breakpoint has been trigged in the last instruction, then return None
        return self.sim.sysHandle.breakpointInfo if self.sim.sysHandle.breakpointTrigged else None

    def step(self, stepMode=None):
        # stepMode= "into" | "forward" | "out" | "run"
        # None means to keep the current mode, whatever it is
        if stepMode is not None:
            self.sim.setStepCondition(stepMode)
        self.sim.nextInstr()

    def stepBack(self, count=1):
        # step back 'count' times
        self.sim.stepBack(count)

    def getMemory(self, addr, returnHexaStr=True):
        val = self.sim.mem.get(addr, 1, mayTriggerBkpt=False)
        if returnHexaStr:
            return "{:02X}".format(unpack("B", val)[0])
        else:
            return val

    def getMemoryFormatted(self):
        return self.sim.mem.serializeFormatted()

    def setMemory(self, addr, val):
        # if addr is not initialized, then do nothing
        # val is a bytearray of one element (1 byte)
        if self.sim.mem._getRelativeAddr(addr, 1) is None:
            return
        self.sim.mem.set(addr, val[0], 1)

    def getCurrentInfos(self):
        # Return [["highlightread", ["r3", "SVC_r12", "z", "sz"]], ["highlightwrite", ["r1", "MEM_adresseHexa"]], ["nextline", 42], ["disassembly", ""]]
        s = self.sim.disassemblyInfo

        # Convert nextline from addr to line number
        idx = [i for i, x in enumerate(s) if x[0] == "nextline"]
        try:
            s[idx[0]][1] = self.addr2line[s[idx[0]][1]][-1]
        except IndexError:
            s = [x for i, x in enumerate(s) if x[0] != "nextline"]

        return s

    def getRegisters(self):
        return self.sim.regs.getAllRegisters()

    def setRegisters(self, regsDict):
        for r,v in regsDict.items():
            self.sim.regs[r].set(v, mayTriggerBkpt=False)
        # Changing the registers may change some infos in the prediction (for instance, memory cells affected by a mem access)
        self.sim.decodeInstr()

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
        # Changing the flags may change the decision to execute or not the next instruction, we update it
        self.sim.decodeInstr()

    def getProcessorMode(self):
        return self.sim.flags.getMode()

    def getCycleCount(self):
        return self.sim.sysHandle.countCycles

    def getChanges(self):
        # Return the modified registers, memory, flags
        #
        d = {}
        dRegsAndFlags, dBank = self.sim.regs.getRegistersAndFlagsChanges()
        if dBank is not None:
            d["bank"] = dBank
        if len(dRegsAndFlags) > 0:
            d["register"] = dRegsAndFlags

        lMem = self.sim.mem.getMemoryChanges()
        if len(lMem) > 0:
            d["memory"] = lMem
        return d

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


