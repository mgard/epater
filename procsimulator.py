import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque

from settings import getSetting
from instruction import BytecodeToInstrInfos, InstrType


class SimulatorError(Exception):
    def __init__(self, desc):
        self.desc = desc
    def __str__(self):
        return self.desc


BkptInfo = namedtuple("BkptInfo", ['source', 'mode', 'infos'])
class SystemHandler:
    def __init__(self, initCountCycles=-1):
        self.breakpointTrigged = None
        self.breakpointInfo = None
        self.countCycles = initCountCycles
        self.clearBreakpoint()

    def clearBreakpoint(self):
        self.breakpointTrigged = False
        self.breakpointInfo = None

    def throw(self, infos):
        self.breakpointTrigged = True
        self.breakpointInfo = infos


class Register:

    def __init__(self, n, systemHandle, val=0, altname=None):
        self.id = n
        self.val = val
        self.sys = systemHandle
        self.altname = altname
        self.breakpoint = 0
        self.history = deque([], getSetting('maxhistorylength'))

    @property
    def name(self):
        return "R{}".format(self.id)

    def get(self, mayTriggerBkpt=True):
        if mayTriggerBkpt and self.breakpoint & 4:
            self.sys.throw(BkptInfo("register", 4, self.id))
        return self.val

    def set(self, val, mayTriggerBkpt=True):
        val &= 0xFFFFFFFF
        if mayTriggerBkpt and self.breakpoint & 2:
            self.sys.throw(BkptInfo("register", 2, self.id))
        self.history.append((self.sys.countCycles, val))
        self.val = val

    def stepBack(self):
        # Set the register as it was one step back
        while self.history[-1][0] >= self.sys.countCycles:
            self.history.pop()
            self.val = self.history[-1][1]

    def getChanges(self):
        if len(self.history) == 0 or self.history[-1][0] != self.sys.countCycles:
            return None
        return self.val


class ControlRegister:
    flag2index = {'N': 31, 'Z': 30, 'C': 29, 'V': 28, 'I': 7, 'F': 6}
    index2flag = {v:k for k,v in flag2index.items()}
    mode2bits = {'User': 16, 'FIQ': 17, 'IRQ': 18, 'SVC': 19}       # Other modes are not supported
    bits2mode = {v:k for k,v in mode2bits.items()}

    def __init__(self, name, systemHandle):
        self.regname = name
        self.sys = systemHandle
        self.val = 0
        self.history = deque([], getSetting('maxhistorylength'))
        self.historyFlags = deque([], getSetting('maxhistorylength'))
        self.setMode("User")
        self.breakpoints = {flag:0 for flag in self.flag2index.keys()}

    @property
    def name(self):
        return self.regname

    def setMode(self, mode):
        if mode not in self.mode2bits:
            raise KeyError
        self.val |= self.mode2bits[mode]
        self.val &= 0xFFFFFFE0 + self.mode2bits[mode]
        self.history.append((self.sys.countCycles, self.val))

    def getMode(self):
        k = self.val & 0x1F
        assert k in self.bits2mode, "Invalid processor mode : {}".format(k)
        return self.bits2mode[k]

    def __getitem__(self, flag):
        flag = flag.upper()
        if flag not in self.flag2index:      # Thumb and Jazelle mode are not implemented
            raise KeyError

        if self.breakpoints[flag] & 4:
            self.sys.throw(BkptInfo("flag", 4, flag))

        return bool((self.val >> self.flag2index[flag]) & 0x1)

    def __setitem__(self, flag, value):
        self.setFlag(flag, value)

    def get(self):
        # Return the content of the PSR as an integer
        return self.val

    def setFlag(self, flag, value, mayTriggerBkpt=True):
        flag = flag.upper()
        if flag not in self.flag2index:
            raise KeyError

        if mayTriggerBkpt and self.breakpoints[flag] & 2:
            self.sys.throw(BkptInfo("flag", 2, flag))

        if value:   # We set the flag
            self.val |= 1 << self.flag2index[flag]
        else:       # We clear the flag
            self.val &= 0xFFFFFFFF - (1 << self.flag2index[flag])
        self.history.append((self.sys.countCycles, self.val))
        if len(self.historyFlags) > 0 and self.historyFlags[-1][0] == self.sys.countCycles:
            self.historyFlags[-1][1].update({flag: value})
        else:
            self.historyFlags.append((self.sys.countCycles, {flag: value}))

    def getAllFlags(self):
        # This function never triggers a breakpoint
        return {flag: bool((self.val >> self.flag2index[flag]) & 0x1) for flag in self.flag2index.keys()}

    def getChanges(self):
        if len(self.historyFlags) == 0 or self.historyFlags[-1][0] != self.sys.countCycles:
            return {}
        return self.historyFlags[-1][1]

    def set(self, val):
        # Be careful with this method, many PSR values are illegal
        # Use setMode and __setitem__ whenever possible!
        # Mostly use for internal purposes like saving the CPSR in SPSR when an interrupt arises
        self.val = val
        self.history.append((self.sys.countCycles, self.val))

    def stepBack(self):
        # Set the program status registers as they were one step back
        while self.history[-1][0] >= self.sys.countCycles:
            self.history.pop()
            self.val = self.history[-1][1]


class BankedRegisters:

    def __init__(self, systemHandle):
        self.sys = systemHandle
        self.history = deque([], getSetting('maxhistorylength'))
        # Create regular registers
        self.banks = {}
        regs = [Register(i, systemHandle) for i in range(16)]
        regs[13].altname = "SP"
        regs[14].altname = "LR"
        regs[15].altname = "PC"
        # We add the flags
        # No SPSR in user mode
        flags = (ControlRegister("CPSR", systemHandle), None)
        self.banks['User'] = (regs, flags)

        # Create FIQ registers
        regsFIQ = regs[:8]          # R0-R7 are shared
        regsFIQ.extend(Register(i, systemHandle) for i in range(8, 15))        # R8-R14 are exclusive
        regsFIQ.append(regs[15])    # PC is shared
        flagsFIQ = (flags[0], ControlRegister("SPSR_fiq", systemHandle))
        self.banks['FIQ'] = (regsFIQ, flagsFIQ)

        # Create IRQ registers
        regsIRQ = regs[:13]         # R0-R12 are shared
        regsIRQ.extend(Register(i, systemHandle) for i in range(13, 15))        # R13-R14 are exclusive
        regsIRQ.append(regs[15])    # PC is shared
        flagsIRQ = (flags[0], ControlRegister("SPSR_irq", systemHandle))
        self.banks['IRQ'] = (regsIRQ, flagsIRQ)

        # Create SVC registers (used with software interrupts)
        regsSVC = regs[:13]  # R0-R12 are shared
        regsSVC.extend(Register(i, systemHandle) for i in range(13, 15))  # R13-R14 are exclusive
        regsSVC.append(regs[15])  # PC is shared
        flagsSVC = (flags[0], ControlRegister("SPSR_svc", systemHandle))
        self.banks['SVC'] = (regsSVC, flagsSVC)

        # By default, we are in user mode
        self.setCurrentBank("User")

    def setCurrentBank(self, bankname, logToHistory=True):
        self.currentBank = bankname
        if logToHistory:
            # Sometimes we just want to switch banks 2 times in the same cycle for internal reasons (like storing
            # registers from User bank in privileged mode), so this optionnal argument controls if this switch has to be
            # logged and transfered to the UI
            self.history.append((self.sys.countCycles, bankname))

    def __getitem__(self, item):
        if not isinstance(item, int) or item < 0 or item > 15:
            raise IndexError
        return self.banks[self.currentBank][0][item]

    def getCPSR(self):
        return self.banks[self.currentBank][1][0]

    def getSPSR(self):
        if self.currentBank == "User":
            return None             # No SPSR register in user mode
        return self.banks[self.currentBank][1][1]

    def getAllRegisters(self):
        # Helper function to get all registers from all banks at once
        # The result is returned as a dictionary of dictionary
        return {bname: {reg.name: reg.get(mayTriggerBkpt=False) for reg in bank[0]} for bname, bank in self.banks.items()}

    def getRegistersAndFlagsChanges(self):
        d = {}
        changeBank = None
        if len(self.history) > 0 and self.history[-1][0] == self.sys.countCycles:
            changeBank = self.history[-1][1]

        prefixBanks = {"User": "", "FIQ": "FIQ_", "IRQ": "IRQ_", "SVC": "SVC_"}
        # Add CPSR flags that were modified in the last cycle
        d.update({flag: val for flag,val in self.getCPSR().getChanges().items()})
        for bank in self.banks:
            # Get registers update
            d.update({"{}{}".format(prefixBanks[bank], reg.name): reg.getChanges() for reg in self.banks[bank][0] if reg.getChanges() is not None})

            if changeBank is not None and self.currentBank != "User":
                # If we just changed bank, we send the whole SPSR, regardless of its changes
                d.update({"S{}".format(flag): val for flag, val in self.getSPSR().getAllFlags().items()})
            elif self.currentBank != "User":
                # Else, we just send the current SPSR changes (if there are any, and if the current bank has a SPSR)
                d.update({"S{}".format(flag): val for flag, val in self.getSPSR().getChanges().items()})

        return d, changeBank

    def stepBack(self):
        # Set the registers and flags as they were one step back
        for bank in self.banks.values():
            for reg in bank:
                reg.stepBack()

        while self.history[-1][0] >= self.sys.countCycles:
            self.history.pop()
            self.currentBank = self.history[-1][1]


class Memory:

    def __init__(self, memcontent, systemHandle, initval=0):
        self.size = sum(len(b) for b in memcontent)
        self.initval = initval
        self.history = deque([], getSetting('maxhistorylength'))
        self.sys = systemHandle
        self.startAddr = memcontent['__MEMINFOSTART']
        self.endAddr = memcontent['__MEMINFOEND']
        self.maxAddr = max(self.endAddr.values())
        assert len(self.startAddr) == len(self.endAddr)

        self.data = {k:bytearray(memcontent[k]) for k in self.startAddr.keys()}
        self.initdata = self.data.copy()

        # Maps address to an integer 'n'. The integer n allows to determine if the breakpoint should be
        # used or not, in the same way of Unix permissions.
        # If n & 4, then it is active for each read operation
        # If n & 2, then it is active for each write operation
        # If n & 1, then it is active for each exec operation (namely, an instruction load)
        self.breakpoints = defaultdict(int)

        self.history = []

    def _getRelativeAddr(self, addr, size):
        """
        Determine if *addr* is a valid address, and return a tuple containing the section
        and offset of this address.
        :param addr: The address we want to check
        :return: None if the address is invalid. Else, a tuple of two elements, the first being the
        section used and the second the offset relative from the start of this section.
        """
        if addr < 0 or addr > self.maxAddr - (size-1):
            return None
        for sec in self.startAddr.keys():
            if self.startAddr[sec] <= addr < self.endAddr[sec] - (size-1):
                return sec, addr - self.startAddr[sec]
        return None

    def get(self, addr, size=4, execMode=False, mayTriggerBkpt=True):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            if execMode:
                desc = "Tentative de lecture d'une instruction a une adresse non initialisée : {}".format(hex(addr))
            else:
                desc = "Acces mémoire en lecture fautif a l'adresse {}".format(hex(addr))
            self.sys.throw(BkptInfo("memory", 8, {'addr': addr, 'desc': desc}))
            return None

        for offset in range(size):
            if execMode and self.breakpoints[addr+offset] & 1:
                self.sys.throw(BkptInfo("memory", 1, addr + offset))
            if mayTriggerBkpt and self.breakpoints[addr+offset] & 4:
                self.sys.throw(BkptInfo("memory", 4, addr + offset))

        sec, offset = resolvedAddr
        return self.data[sec][offset:offset+size]

    def set(self, addr, val, size=4, mayTriggerBkpt=True):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            self.sys.throw(BkptInfo("memory", 8, addr))
            return

        for offset in range(size):
            if mayTriggerBkpt and self.breakpoints[addr+offset] & 2:
                self.sys.throw(BkptInfo("memory", 2, addr + offset))

        sec, offset = resolvedAddr
        val &= 0xFFFFFFFF if size == 4 else 0xFF
        valBytes = struct.pack("<I", val) if size == 4 else struct.pack("<B", val)
        self.history.append((self.sys.countCycles, sec, offset, addr, size, val, self.data[sec][offset:offset+size], valBytes))
        self.data[sec][offset:offset+size] = valBytes

    def serialize(self):
        """
        Serialize the memory, useful to be displayed.
        """
        sorted_mem = sorted(self.startAddr.items(), key=operator.itemgetter(1))
        ret_val = bytearray()
        for sec, start in sorted_mem:
            padding_size = start - len(ret_val)
            ret_val += bytearray('\0' * padding_size, 'utf-8')

            ret_val += self.data[sec]

            padding_size = self.endAddr[sec] - start - len(self.data[sec])
            ret_val += bytearray('\0' * padding_size, 'utf-8')
        return ret_val

    def serializeFormatted(self):
        # Return a list of strings of length 2
        # These strings may contain the hex value of the mem cell, or "--" to indicate that it is undeclared
        sorted_mem = sorted(self.startAddr.items(), key=operator.itemgetter(1))
        retList = []
        for sec, start in sorted_mem:
            padding_size = start - len(retList)
            retList += ["--"] * padding_size

            retList += ["{:02X}".format(d) for d in self.data[sec]]

            padding_size = self.endAddr[sec] - start - len(self.data[sec])
            retList += ["--"] * padding_size
        return retList

    def getMemoryChanges(self):
        if len(self.history) == 0:
            return []

        changesList = []
        for step in self.history[::-1]:
            cycle, sec, offset, virtualAddr, size, val, previousValBytes, valBytes = step
            if cycle == self.sys.countCycles:
                changesList.extend([[virtualAddr+dec, int(valBytes[dec])] for dec in range(size)])
            else:
                # Since we iterate from the end, the cycle numbers will always decrease, so it is useless to continue
                break
        return changesList

    def setBreakpoint(self, addr, modeOctal):
        self.breakpoints[addr] = modeOctal

    def toggleBreakpoint(self, addr, modeOctal):
        if not addr in self.breakpoints:
            self.setBreakpoint(addr, modeOctal)
        else:
            # Toggle the value
            self.breakpoints[addr] ^= modeOctal

    def removeBreakpoint(self, addr):
        self.breakpoints[addr] = 0

    def removeExecuteBreakpoints(self, ignoreList=()):
        # Remove all execution breakpoints, except for those that have their address in ignoreList
        for addr in [a for a,b in self.breakpoints.items() if b & 1 == 1 and a not in ignoreList]:
            self.removeBreakpoint(addr)

    def stepBack(self):
        # Set the memory as it was one step back in the past
        while self.history[-1][0] >= self.sys.countCycles:
            _, sec, offset, virtualAddr, size, val, previousValBytes,  = self.history.pop()
            self.data[sec][offset:offset+size] = previousValBytes



class SimState(Enum):
    undefined = -1
    uninitialized = 0
    ready = 1
    started = 2
    stopped = 3
    finished = 4

class Simulator:

    def __init__(self, memorycontent):
        self.state = SimState.uninitialized
        self.sysHandle = SystemHandler()
        self.mem = Memory(memorycontent, self.sysHandle)
        self.pcoffset = 8 if getSetting("PCbehavior") == "+8" else 0

        self.interruptActive = False
        self.interruptParams = {'b': 0, 'a': 0, 't0': 0, 'type': "FIQ"}       # Interrupt trigged at each a*(t-t0) + b cycles
        self.lastInterruptCycle = -1

        self.regs = BankedRegisters(self.sysHandle)

        self.stepMode = None
        self.stepCondition = 0
        self.runIteration = 0           # Used to stop the simulator after n iterations in run mode

        self.flags = self.regs.getCPSR()

        self.fetchedInstr = None

    def reset(self):
        self.state = SimState.ready
        self.sysHandle.countCycle = 0
        self.regs[15].set(self.pcoffset)
        # We fetch the first instruction
        self.fetchedInstr = bytes(self.mem.get(self.regs[15].get() - self.pcoffset, execMode=True))

    def _printState(self):
        """
        Debug function
        :return:
        """
        pass

    def isStepDone(self):
        if self.stepMode == "forward":
            if self.stepCondition == 2:
                # The instruction was a function call
                # Now the step forward becomes a step out
                self.stepMode = "out"
                self.stepCondition = 1
            else:
                return True
        if self.stepMode == "out":
            return self.stepCondition == 0
        if self.stepMode == "run":
            return self.sysHandle.countCycles - self.runIteration >= getSetting("runmaxit")

        # We are doing a step into, we always stop
        return True


    def setStepCondition(self, stepMode):
        assert stepMode in ("into", "out", "forward", "run")
        self.stepMode = stepMode
        self.stepCondition = 1
        self.runIteration = self.sysHandle.countCycles


    def stepBack(self, count):
        for i in range(count):
            self.mem.stepBack()
            self.regs.stepBack()
            self.sysHandle.countCycles -= 1             # We decrement the cycle counter


    def _shiftVal(self, val, shiftInfo):
        shiftamount = self.regs[shiftInfo[2]].get() & 0xF if shiftInfo[1] == 'reg' else shiftInfo[2]
        carryOut = 0
        if shiftInfo[0] == "LSL":
            carryOut = (val >> (32-shiftamount)) & 1
            val = (val << shiftamount) & 0xFFFFFFFF
        elif shiftInfo[0] == "LSR":
            carryOut = (val >> (shiftamount-1)) & 1
            val = (val >> shiftamount) & 0xFFFFFFFF
        elif shiftInfo[0] == "ASR":
            carryOut = (val >> (shiftamount-1)) & 1
            firstBit = (val >> 31) & 1
            val = ((val >> shiftamount) & 0xFFFFFFFF) | (2**(shiftamount+1) << (32-shiftamount))
        elif shiftInfo[0] == "ROR":
            if shiftamount == 0:
                # The form of the shift field which might be expected to give ROR #0 is used to encode
                # a special function of the barrel shifter, rotate right extended (RRX).
                carryOut = val & 1
                val = (val >> 1) | (int(self.flags['C']) << 31)
            else:
                carryOut = (val >> (shiftamount-1)) & 1
                val = ((val & (2**32-1)) >> shiftamount%32) | (val << (32-(shiftamount%32)) & (2**32-1))
        return carryOut, val

    def _checkCarry(self, op1, op2, res):
        return bool(res & (1 << 32))

    def _checkOverflow(self, op1, op2, res):
        if not bool((op1 & 0x80000000) ^ (op2 & 0x80000000)):
            return not bool((op1 & 0x80000000) ^ (res & 0x80000000))
        return False

    def execInstr(self):
        """
        Execute one instruction
        :param addr: Address of the instruction in memory
        :return: a boolean indicating if PC was modified by the current instruction
        This function may throw a SimulatorError exception if there's an error, or a Breakpoint exception,
        in which case it is not an error but rather a Breakpoint reached.
        """

        # Decode it
        t, regs, cond, misc = BytecodeToInstrInfos(self.fetchedInstr)
        workingFlags = {}
        pcchanged = False

        # Check condition
        # Warning : here we check if the condition is NOT met, hence we use the
        # INVERSE of the actual condition
        # See Table 4-2 of ARM7TDMI data sheet as reference of these conditions
        if (cond == "EQ" and not self.flags['Z'] or
            cond == "NE" and self.flags['Z'] or
            cond == "CS" and not self.flags['C'] or
            cond == "CC" and self.flags['C'] or
            cond == "MI" and not self.flags['N'] or
            cond == "PL" and self.flags['N'] or
            cond == "VS" and not self.flags['V'] or
            cond == "VC" and self.flags['V'] or
            cond == "HI" and (not self.flags['C'] or self.flags['Z']) or
            cond == "LS" and (self.flags['C'] and not self.flags['Z']) or
            cond == "GE" and not self.flags['V'] == self.flags['N'] or
            cond == "LT" and self.flags['V'] == self.flags['N'] or
            cond == "GT" and (self.flags['Z'] or self.flags['V'] != self.flags['N']) or
            cond == "LE" and (not self.flags['Z'] and self.flags['V'] == self.flags['N'])):
            # Condition not met, return
            return pcchanged

        # Execute it
        if t == InstrType.softinterrupt:
            # We enter a software interrupt
            self.regs.setCurrentBank("SVC")                     # Set the register bank
            self.regs.getSPSR().set(self.regs.getCPSR().get())  # Save the CPSR in the current SPSR
            self.regs.getCPSR().setMode("SVC")                  # Set the interrupt mode in CPSR
            # Does entering SVC interrupt deactivate IRQ and/or FIQ?
            self.regs[14].set(self.regs[15].get())              # Save PC in LR_svc
            self.regs[15].set(0x08)                             # Set PC to enter the interrupt
            pcchanged = True

        elif t == InstrType.nopop:
            pass        # Nothing to do

        elif t == InstrType.branch:
            if misc['L']:       # Link
                self.regs[14].set(self.regs[15].get() - self.pcoffset + 4)
                self.stepCondition += 1         # We are entering a function, we log it (useful for stepForward and stepOut)
            if misc['mode'] == 'imm':
                self.regs[15].set(self.regs[15].get() + misc['offset'])
            else:   # BX
                self.regs[15].set(self.regs[misc['offset']].get())
                self.stepCondition -= 1         # We are returning from a function, we log it (useful for stepForward and stepOut)
            pcchanged = True

        elif t == InstrType.memop:
            addr = baseval = self.regs[misc['base']].get()
            if misc['imm']:
                addr += misc['sign'] * misc['offset']
            else:
                _, sval = self._shiftVal(self.regs[misc['offset'][0]].get(), misc['offset'][1])
                addr += misc['sign'] * sval

            realAddr = addr if misc['pre'] else baseval
            if misc['mode'] == 'LDR':
                m = self.mem.get(realAddr, size=1 if misc['byte'] else 4)
                if m is None:       # No such address in the mapped memory, we cannot continue
                    return False
                res = struct.unpack("<I", m)[0]
                self.regs[misc['rd']].set(res)
            else:       # STR
                valWrite = self.regs[misc['rd']].get()
                if misc['rd'] == 15 and getSetting("PCspecialbehavior"):
                    valWrite += 4       # Special case for PC (see ARM datasheet, 4.9.4)
                self.mem.set(realAddr, valWrite, size=1 if misc['byte'] else 4)

            if misc['writeback']:
                self.regs[misc['base']].set(addr)

        elif t == InstrType.multiplememop:
            # "The lowest-numbereing register is stored to the lowest memory address, through the
            # highest-numbered register to the highest memory address"
            baseAddr = self.regs[misc['base']].get()
            if misc['pre']:
                baseAddr += misc['sign'] * 4

            currentbank = self.regs.currentBank
            if currentbank != "User" and misc['sbit'] and (misc['mode'] == "STR" or 15 not in regs):
                # "For both LDM and STM instructions, the User bank registers are transferred rather thathe register
                #  bank corresponding to the current mode. This is useful for saving the usestate on process switches.
                #  Base write-back should not be used when this mechanism is employed."
                self.regs.setCurrentBank("User", logToHistory=False)

            if misc['mode'] == 'LDR':
                for reg in regs[::misc['sign']]:
                    m = self.mem.get(baseAddr, size=4)
                    val = struct.unpack("<I", m)[0]
                    self.regs[reg].set(val)
                    baseAddr += misc['sign'] * 4
                if misc['sbit'] and 15 in regs:
                    # "If the instruction is a LDM then SPSR_<mode> is transferred to CPSR at the same time as R15 is loaded."
                    self.regs.getCPSR().set(self.regs.getSPSR().get())
            else:   # STR
                for reg in regs[::misc['sign']]:
                    val = self.regs[reg].get()
                    self.mem.set(baseAddr, val, size=4)
                    baseAddr += misc['sign'] * 4
            if misc['pre']:
                baseAddr -= misc['sign'] * 4        # If we are in pre-increment mode, we remove the last increment

            if misc['writeback']:
                # Technically, it will break if we use a different bank (e.g. the S bit is set), but the ARM spec
                # explicitely says that "Base write-back should not be used when this mechanism (the S bit) is employed".
                # Maybe we could output an explicit error if this is the case?
                self.regs[misc['base']].set(baseAddr)

            if currentbank != self.regs.currentBank:
                self.regs.setCurrentBank(currentbank, logToHistory=False)


        elif t == InstrType.psrtransfer:
            if misc['write']:
                if misc['flagsOnly']:
                    if misc['imm']:
                        valToSet = misc['op2'][0]
                        if misc['op2'][1][2] != 0:
                            _, valToSet = self._shiftVal(valToSet, misc['op2'][1])
                    else:
                        valToSet = self.regs[misc['op2'][0]] & 0xF0000000   # We only keep the condition flag bits
                else:
                    valToSet = self.regs[misc['op2'][0]]
                if misc['usespsr']:
                    self.regs.getSPSR().set(valToSet)
                else:
                    self.regs.getCPSR().set(valToSet)
            else:       # Read
                self.regs[misc['rd']].set(self.regs.getSPSR().get() if misc['usespsr'] else self.regs.getCPSR().get())

        elif t == InstrType.dataop:
            workingFlags['C'] = 0
            workingFlags['V'] = 0
            # Get first operand value
            op1 = self.regs[misc['rn']].get()
            # Get second operand value
            if misc['imm']:
                op2 = misc['op2'][0]
                if misc['op2'][1][2] != 0:
                    carry, op2 = self._shiftVal(op2, misc['op2'][1])
                    workingFlags['C'] = bool(carry)
            else:
                op2 = self.regs[misc['op2'][0]].get()
                if misc['op2'][0] == 15 and getSetting("PCspecialbehavior"):
                    op2 += 4    # Special case for PC where we use PC+12 instead of PC+8 (see 4.5.5 of ARM Instr. set)
                carry, op2 = self._shiftVal(op2, misc['op2'][1])
                workingFlags['C'] = bool(carry)

            # Get destination register and write the result
            destrd = misc['rd']

            if misc['opcode'] in ("AND", "TST"):
                # These instructions do not affect the V flag (ARM Instr. set, 4.5.1)
                # However, C flag "is set to the carry out from the barrel shifter [if the shift is not LSL #0]" (4.5.1)
                # this was already done when we called _shiftVal
                res = op1 & op2
            elif misc['opcode'] in ("EOR", "TEQ"):
                # These instructions do not affect the C and V flags (ARM Instr. set, 4.5.1)
                res = op1 ^ op2
            elif misc['opcode'] in ("SUB", "CMP"):
                res = op1 - op2
                workingFlags['C'] = self._checkCarry(op1, op2, res)
                workingFlags['V'] = self._checkOverflow(op1, (~op2)+1, res)
            elif misc['opcode'] == "RSB":
                res = op2 - op1
                workingFlags['C'] = self._checkCarry(op2, op1, res)
                workingFlags['V'] = self._checkOverflow(op2, (~op1)+1, res)
            elif misc['opcode'] in ("ADD", "CMN"):
                res = op1 + op2
                workingFlags['C'] = self._checkCarry(op1, op2, res)
                workingFlags['V'] = self._checkOverflow(op1, op2, res)
            elif misc['opcode'] == "ADC":
                res = op1 + op2 + int(self.flags['C'])
                workingFlags['C'] = self._checkCarry(op1, op2 + int(self.flags['C']), res)
                workingFlags['V'] = self._checkOverflow(op1, op2 + int(self.flags['C']), res)
            elif misc['opcode'] == "SBC":
                res = op1 - op2 + int(self.flags['C']) - 1
                workingFlags['C'] = self._checkCarry(op1, op2 + int(self.flags['C']) - 1, res)
                workingFlags['V'] = self._checkOverflow(op1, ((~op2) + 1) + int(self.flags['C']) - 1, res)
            elif misc['opcode'] == "RSC":
                res = op2 - op1 + int(self.flags['C']) - 1
                workingFlags['C'] = self._checkCarry(op2, op1 + int(self.flags['C']) - 1, res)
                workingFlags['V'] = self._checkOverflow(op2, ((~op1) + 1) + int(self.flags['C']) - 1, res)
            elif misc['opcode'] == "ORR":
                res = op1 | op2
            elif misc['opcode'] == "MOV":
                res = op2
            elif misc['opcode'] == "BIC":
                res = op1 & ~op2     # Bit clear?
            elif misc['opcode'] == "MVN":
                res = ~op2
            else:
                assert False, "Bad data opcode : " + misc['opcode']

            res &= 0xFFFFFFFF           # Get the result back to 32 bits, if applicable (else it's just a no-op)

            workingFlags['Z'] = res == 0
            workingFlags['N'] = res & 0x80000000            # "N flag will be set to the value of bit 31 of the result" (4.5.1)

            if destrd == 15:
                pcchanged = True

            if misc['setflags']:
                if destrd == 15:
                    # Combining writing to PC and the S flag is a special case (see ARM Instr. set, 4.5.5)
                    # "When Rd is R15 and the S flag is set the result of the operation is placed in R15 and
                    # the SPSR corresponding to the current mode is moved to the CPSR. This allows state
                    # changes which atomically restore both PC and CPSR. This form of instruction should
                    # not be used in User mode."
                    #
                    # Globally, it tells out to get out of an interrupt
                    if self.regs.getCPSR().getMode() == "User":
                        assert False, "Error, using S flag and PC as destination register in user mode!"
                    self.regs.getCPSR().set(self.regs.getSPSR().get())          # Put back the saved SPSR in CPSR
                else:
                    for flag in workingFlags:
                        self.flags[flag] = workingFlags[flag]
            if misc['opcode'] not in ("TST", "TEQ", "CMP", "CMN"):
                # We actually write the result
                self.regs[destrd].set(res)

        return pcchanged

    def nextInstr(self):
        # One more cycle to do!
        self.sysHandle.countCycles += 1

        # We clear an eventual breakpoint
        self.sysHandle.clearBreakpoint()

        # The instruction should have been fetched by the last instruction
        pcmodified = self.execInstr()
        if pcmodified:
            self.regs[15].set(self.regs[15].get() + self.pcoffset)
        else:
            self.regs[15].set(self.regs[15].get() + 4)        # PC = PC + 4

        # We look for interrupts
        # The current instruction is always finished before the interrupt
        # TODO Handle special cases for LDR and STR multiples
        if self.interruptActive and (self.lastInterruptCycle == -1 and self.sysHandle.countCycles - self.interruptParams['b'] >= self.interruptParams['t0'] or
                                        self.lastInterruptCycle >= 0 and self.sysHandle.countCycles - self.lastInterruptCycle >= self.interruptParams['a']):
            if (self.interruptParams['type'] == "FIQ" and not self.regs.getCPSR()['F'] or
                    self.interruptParams['type'] == "IRQ" and not self.regs.getCPSR()['I']):        # Is the interrupt masked?
                # Interruption!
                # We enter it (the entry point is 0x18 for IRQ and 0x1C for FIQ)
                self.regs.setCurrentBank(self.interruptParams['type'])                  # Set the register bank
                self.regs.getSPSR().set(self.regs.getCPSR().get())                      # Save the CPSR in the current SPSR
                self.regs.getCPSR().setMode(self.interruptParams['type'])               # Set the interrupt mode in CPSR
                self.regs.getCPSR()[self.interruptParams['type'][0]] = True             # Disable interrupts
                self.regs[14].set(self.regs[15].get() - 4)                              # Save PC in LR (on the FIQ or IRQ bank)
                self.regs[15].set(self.pcoffset + (0x18 if self.interruptParams['type'] == "IRQ" else 0x1C))      # Set PC to enter the interrupt
                self.lastInterruptCycle = self.sysHandle.countCycles

        # Retrieve instruction from memory
        nextInstrBytes = self.mem.get(self.regs[15].get() - self.pcoffset, execMode=True)
        if nextInstrBytes is not None:          # We did not make an illegal memory access
            self.fetchedInstr = bytes(nextInstrBytes)

        # Question : if we hit a breakpoint for the _next_ instruction, should we enter the interrupt anyway?
        # Did we hit a breakpoint?
        # A breakpoint always stop the simulator
        if self.sysHandle.breakpointTrigged:
            self.stepMode = None


