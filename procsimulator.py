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
        self.breakpointInfo = []

    def throw(self, infos):
        self.breakpointTrigged = True
        self.breakpointInfo.append(infos)


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
        while (len(self.history) > 0) and (self.history[-1][0] >= self.sys.countCycles):
            self.val = self.history[-1][1]
            self.history.pop()

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
        self.val &= 0xFFFFFFE0                  # Reset the mode
        self.val |= self.mode2bits[mode]        # Set the mode wanted
        #self.val &= 0xFFFFFFE0 + self.mode2bits[mode]
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
        self.setFlag(flag, bool(value))

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
        seqFlags = ('N', 'Z', 'C', 'V')
        seqVals = [bool(self.val & (1 << self.flag2index[flag])) for flag in seqFlags]
        self.historyFlags.append((self.sys.countCycles, dict(zip(seqFlags, seqVals))))

    def stepBack(self):
        # Set the program status registers as they were one step back
        while (len(self.history) > 0) and (self.history[-1][0] >= self.sys.countCycles):
            self.val = self.history[-1][1]
            self.history.pop()


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

    def setCurrentBankFromMode(self, modeInt, logToHistory=True):
        self.currentBank = ControlRegister.bits2mode[modeInt]
        if logToHistory:
            self.history.append((self.sys.countCycles, self.currentBank))

    def __getitem__(self, item):
        if not isinstance(item, int) or item < 0 or item > 15:
            raise IndexError
        return self.banks[self.currentBank][0][item]

    def getRegisterFromBank(self, bank, item):
        return self.banks[bank][0][item]

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
            for reg in bank[0]:
                reg.stepBack()
            for flag in [f for f in bank[1] if f]:
                flag.stepBack()

        while (len(self.history) > 0) and (self.history[-1][0] >= self.sys.countCycles):
            self.currentBank = self.history[-1][1]
            self.history.pop()


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
            self.sys.throw(BkptInfo("memory", 8, desc))
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
            self.sys.throw(BkptInfo("memory", 8, "Accès invalide pour une écriture de taille {} à l'adresse {}".format(size, hex(addr))))
            return

        for offset in range(size):
            if mayTriggerBkpt and self.breakpoints[addr+offset] & 2:
                self.sys.throw(BkptInfo("memory", 2, addr + offset))

        sec, offset = resolvedAddr
        val &= 0xFFFFFFFF if size == 4 else 0xFF
        valBytes = struct.pack("<I", val) if size == 4 else struct.pack("<B", val)
        histidx = -1
        while -histidx <= len(self.history) and self.history[histidx][0] == self.sys.countCycles:
            prevhist = self.history[histidx]
            if prevhist[3] == addr and prevhist[4] == size:
                # We modified the same memory address twice in the same cycle, we only keep the last one
                self.history.pop(histidx)
            histidx -= 1
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
        return self.breakpoints[addr]

    def removeBreakpoint(self, addr):
        self.breakpoints[addr] = 0

    def removeExecuteBreakpoints(self, removeList=()):
        # Remove all execution breakpoints, except for those that have their address in ignoreList
        for addr in [a for a,b in self.breakpoints.items() if b & 1 == 1 and a in removeList]:
            self.removeBreakpoint(addr)

    def stepBack(self):
        # Set the memory as it was one step back in the past
        while (len(self.history) > 0) and (self.history[-1][0] >= self.sys.countCycles):
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

    def __init__(self, memorycontent, assertionTriggers, addr2line):
        self.state = SimState.uninitialized
        self.sysHandle = SystemHandler()
        self.mem = Memory(memorycontent, self.sysHandle)
        self.assertionCkpts = set(assertionTriggers.keys())
        self.assertionData = assertionTriggers
        self.assertionWhenReturn = set()
        self.pcoffset = 8 if getSetting("PCbehavior") == "+8" else 0
        self.callStack = []

        self.addr2line = addr2line

        self.interruptActive = False
        self.interruptParams = {'b': 0, 'a': 0, 't0': 0, 'type': "FIQ"}       # Interrupt trigged at each a*(t-t0) + b cycles
        self.lastInterruptCycle = -1

        self.regs = BankedRegisters(self.sysHandle)

        self.stepMode = None
        self.stepCondition = 0
        self.runIteration = 0           # Used to stop the simulator after n iterations in run mode

        self.flags = self.regs.getCPSR()

        self.fetchedInstr = None
        self.decodedInstr = None
        self.disassemblyInfo = ""

    def fetchAndDecode(self):
        # Check if PC is valid (multiple of 4)
        if (self.regs[15].get() - self.pcoffset) % 4 != 0:
            self.sysHandle.throw(BkptInfo("pc", None, ("Erreur : la valeur de PC ({}) est invalide (ce doit être un multiple de 4)!".format(hex(self.regs[15].get())))))
        # Retrieve instruction from memory
        self.fetchedInstr = self.mem.get(self.regs[15].get() - self.pcoffset, execMode=True)
        if self.fetchedInstr is not None:          # We did not make an illegal memory access
            self.fetchedInstr = bytes(self.fetchedInstr)

        # Decode instruction
        self.decodedInstr = None
        if self.fetchedInstr is not None:
            self.decodedInstr = BytecodeToInstrInfos(self.fetchedInstr)
            self.decodeInstr()

    def reset(self):
        self.state = SimState.ready
        self.sysHandle.countCycle = 0
        self.regs[15].set(self.pcoffset)
        # We fetch the first instruction
        self.fetchAndDecode()
        # Did we hit a breakpoint?
        # A breakpoint always stop the simulator
        if self.sysHandle.breakpointTrigged:
            self.stepMode = None


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
            carryOut = (val << (32-shiftamount)) & 2**31
            val = (val << shiftamount) & 0xFFFFFFFF
        elif shiftInfo[0] == "LSR":
            if shiftamount == 0:
                # Special case : "The form of the shift field which might be expected to correspond to LSR #0 is used to
                # encode LSR #32, which has a zero result with bit 31 of Rm as the carry output."
                val = 0
                carryOut = (val >> 31) & 1
            else:
                carryOut = (val >> (shiftamount-1)) & 1
                val = (val >> shiftamount) & 0xFFFFFFFF
        elif shiftInfo[0] == "ASR":
            if shiftamount == 0:
                # Special case : "The form of the shift field which might be expected to give ASR #0 is used to encode
                # ASR #32. Bit 31 of Rm is again used as the carry output, and each bit of operand 2 is
                # also equal to bit 31 of Rm. The result is therefore all ones or all zeros, according to the
                # value of bit 31 of Rm."
                carryOut = (val >> 31) & 1
                val = 0 if carryOut == 0 else 0xFFFFFFFF
            else:
                carryOut = (val >> (shiftamount-1)) & 1
                firstBit = (val >> 31) & 1
                val = (val >> shiftamount) | ((val >> 31) * ((2**shiftamount-1) << (32-shiftamount)))
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

    def _addWithCarry(self, op1, op2, carryIn):
        def toSigned(n):
            return n - 2**32 if n & 0x80000000 else n
        # See AddWithCarry() definition, p.40 (A2-8) of ARM Architecture Reference Manual
        op1 &= 0xFFFFFFFF
        op2 &= 0xFFFFFFFF
        usum = op1 + op2 + int(carryIn)
        ssum = toSigned(op1) + toSigned(op2) + int(carryIn)
        r = usum & 0xFFFFFFFF
        carryOut = usum != r
        overflowOut = ssum != toSigned(r)
        return r, carryOut, overflowOut

    def execAssert(self, assertionsList, mode):
        for assertionInfo in assertionsList:
            assertionType = assertionInfo[0]
            if assertionType != mode:
                continue
            assertionLine = assertionInfo[1] - 1
            assertionInfo = assertionInfo[2].split(",")

            strError = ""
            for info in assertionInfo:
                info = info.strip()
                target, value = info.split("=")
                if target[0] == "R":
                    # Register
                    reg = int(target[1:])
                    val = int(value, base=0) & 0xFFFFFFFF
                    valreg = self.regs[reg].get()
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
                        strError += "Erreur : l'adresse mémoire {} devrait contenir {}, mais elle contient {}\n".format(target, val, valmem)
                elif len(target) == 1 and target in ('Z', 'V', 'N', 'C', 'I', 'F'):
                    # Flag
                    val = bool(value)
                    if self.flags[target] != val:
                        strError += "Erreur : le drapeau {} devrait signaler {}, mais il signale {}\n".format(target, val, self.flags[target])
                else:
                    # Assert type unknown
                    strError += "Assertion inconnue!".format(target, val)

            if len(strError) > 0:
                self.sysHandle.throw(BkptInfo("assert", None, (assertionLine, strError)))

    def decodeInstr(self):
        """
        Decode the current instruction in self.decodedInstr
        :return:
        """
        if self.decodedInstr is None:
            # May happen if the user changes the flags while PC holds an illegal value
            return
        t, regs, cond, misc = self.decodedInstr

        pcchanged = False
        highlightread = []
        highlightwrite = []
        nextline = -1
        disassembly = ""
        description = "<ol>\n"
        if cond != 'AL':
            description += "<li>Vérifie si la condition {} est remplie</li>\n".format(cond)

        def _shiftToDescription(shiftInfo):
            if shiftInfo[2] == 0 and shiftInfo[0] == "LSL" and shiftInfo[1] != 'reg':
                # No shift
                return ""

            desc = "("
            if shiftInfo[0] == "LSL":
                desc += "décalé vers la gauche (mode LSL)"
            elif shiftInfo[0] == "LSR":
                desc += "décalé vers la droite (mode LSR)"
            elif shiftInfo[0] == "ASR":
                desc += "décalé vers la droite (mode ASR)"
            elif shiftInfo[0] == "ROR":
                if shiftInfo[2] == 0:
                    desc += "permuté vers la droite avec retenue (mode RRX)"
                else:
                    desc += "permuté vers la droite (mode ROR)"

            if shiftInfo[1] == 'reg':
                desc += " du nombre de positions contenu dans {}".format(_regSuffixWithBank(shiftInfo[2]))
            else:
                desc += " de {} {}".format(shiftInfo[2], "positions" if shiftInfo[2] > 1 else "position")

            desc += ")"
            return desc

        def _shiftToInstruction(shiftInfo):
            if shiftInfo[2] == 0 and shiftInfo[0] == "LSL" and shiftInfo[1] != 'reg':
                # No shift
                return ""

            str = ", " + shiftInfo[0]
            if shiftInfo[0] == "ROR" and shiftInfo[2] == 0:
                str = ", RRX"
            if shiftInfo[1] == 'reg':
                str += " R{}".format(shiftInfo[2])
            else:
                str += " #{}".format(shiftInfo[2])
            return str

        def _registerWithCurrentBank(reg):
            prefixBanks = {"User": "", "FIQ": "FIQ_", "IRQ": "IRQ_", "SVC": "SVC_"}
            listAffectedRegs = ["{}r{}".format(prefixBanks[self.regs.currentBank], reg)]

            if self.regs.currentBank == "User":
                if reg < 13 or reg == 15:
                    listAffectedRegs.append("IRQ_r{}".format(reg))
                    listAffectedRegs.append("SVC_r{}".format(reg))
                if reg < 8 or reg == 15:
                    listAffectedRegs.append("FIQ_r{}".format(reg))
            elif self.regs.currentBank == "IRQ":
                if reg < 13 or reg == 15:
                    listAffectedRegs.append("r{}".format(reg))
                    listAffectedRegs.append("SVC_r{}".format(reg))
                if reg < 8 or reg == 15:
                    listAffectedRegs.append("FIQ_r{}".format(reg))
            elif self.regs.currentBank == "SVC":
                if reg < 13 or reg == 15:
                    listAffectedRegs.append("r{}".format(reg))
                    listAffectedRegs.append("IRQ_r{}".format(reg))
                if reg < 8 or reg == 15:
                    listAffectedRegs.append("FIQ_r{}".format(reg))
            elif self.regs.currentBank == "FIQ":
                if reg < 8 or reg == 15:
                    listAffectedRegs.append("r{}".format(reg))
                    listAffectedRegs.append("IRQ_r{}".format(reg))
                    listAffectedRegs.append("SVC_r{}".format(reg))
            return listAffectedRegs

        def _regSuffixWithBank(reg):
            regStr = "R{}".format(reg) if reg < 13 else ["SP", "LR", "PC"][reg-13]
            if self.regs.currentBank == "FIQ" and 7 < reg < 15:
                return "{}_fiq".format(regStr)
            elif self.regs.currentBank == "IRQ" and 12 < reg < 15:
                return "{}_irq".format(regStr)
            elif self.regs.currentBank == "SVC" and 12 < reg < 15:
                return "{}_svc".format(regStr)
            return regStr

        instrWillExecute = True
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
            instrWillExecute = False

        mappingFlagsCond = {"EQ": ['z'],
                                "NE": ['z'],
                                "CS": ['c'],
                                "CC": ['c'],
                                "MI": ['n'],
                                "PL": ['n'],
                                "VS": ['v'],
                                "VC": ['v'],
                                "HI": ['c', 'z'],
                                "LS": ['c', 'z'],
                                "GE": ['v', 'n'],
                                "LT": ['v', 'n'],
                                "GT": ['v', 'n', 'z'],
                                "LE": ['v', 'n', 'z'],
                                "AL": [],
                                }
        if t != InstrType.undefined:
            highlightread.extend(mappingFlagsCond[cond])

        if t == InstrType.softinterrupt:
            # We enter a software interrupt
            description += "<li>Changement de banque de registres vers SVC</li>\n"
            description += "<li>Copie du CPSR dans le SPSR_svc</li>\n"
            description += "<li>Copie de PC dans LR_svc</li>\n"
            description += "<li>Assignation de 0x08 dans PC</li>\n"
            disassembly = "SVC 0x{:X}".format(misc)

        elif t == InstrType.nopop:
            disassembly = "NOP"
            description += "<li>Ne rien faire</li><li>Nonon, vraiment, juste rien</li>"

        elif t == InstrType.undefined:
            disassembly = "INDÉFINI"
            description = "Instruction indéfinie pour le jeu d'instruction ARM."

        elif t == InstrType.branch:
            disassembly = "B"
            if misc['L']:       # Link
                nextline = self.regs[15].get() - self.pcoffset + 4
                disassembly += "L"
                highlightwrite.extend(_registerWithCurrentBank(14))
                highlightread.extend(_registerWithCurrentBank(15))
                description += "<li>Copie la valeur de {}-4 (l'adresse de la prochaine instruction) dans {}</li>\n".format(_regSuffixWithBank(15), _regSuffixWithBank(14))
            if misc['mode'] == 'imm':
                nextline = self.regs[15].get() + misc['offset']
                highlightread.extend(_registerWithCurrentBank(15))
                highlightwrite.extend(_registerWithCurrentBank(15))
                valAdd = misc['offset']
                if valAdd < 0:
                    description += "<li>Soustrait la valeur {} à {}</li>\n".format(-valAdd, _regSuffixWithBank(15))
                else:
                    description += "<li>Additionne la valeur {} à {}</li>\n".format(valAdd, _regSuffixWithBank(15))
            else:   # BX
                disassembly += "X"
                nextline = self.regs[misc['offset']].get()
                highlightread.extend(_registerWithCurrentBank(misc['offset']))
                highlightwrite.extend(_registerWithCurrentBank(15))
                description += "<li>Copie la valeur de {} dans {}</li>\n".format(_regSuffixWithBank(misc['offset']), _regSuffixWithBank(15))
            pcchanged = True

            disassembly += cond if cond != 'AL' else ""
            disassembly += " {}".format(hex(valAdd)) if misc['mode'] == 'imm' else " R{}".format(misc['offset'])
            if not instrWillExecute:
                nextline = self.regs[15].get() + 4 - self.pcoffset

        elif t == InstrType.memop:
            highlightread = _registerWithCurrentBank(misc['base'])
            addr = baseval = self.regs[misc['base']].get(mayTriggerBkpt=False)

            description += "<li>Utilise la valeur du registre {} comme adresse de base</li>\n".format(_regSuffixWithBank(misc['base']))
            descoffset = ""
            if misc['imm']:
                addr += misc['sign'] * misc['offset']
                if misc['offset'] > 0:
                    descoffset = "<li>Additionne la constante {} à l'adresse de base</li>\n".format(misc['sign'] * misc['offset'])
            else:
                shiftDesc = _shiftToDescription(misc['offset'][1])
                if misc['sign'] > 0:
                    descoffset = "<li>Additionne le registre {} {} à l'adresse de base</li>\n".format(_regSuffixWithBank(misc['offset'][0]), shiftDesc)
                else:
                    descoffset = "<li>Soustrait le registre {} {} à l'adresse de base</li>\n".format(_regSuffixWithBank(misc['offset'][0]), shiftDesc)
                _, sval = self._shiftVal(self.regs[misc['offset'][0]].get(), misc['offset'][1])
                addr += misc['sign'] * sval
                highlightread.extend(_registerWithCurrentBank(misc['offset'][0]))

            realAddr = addr if misc['pre'] else baseval
            sizeaccess = 1 if misc['byte'] else 4
            if misc['mode'] == 'LDR':
                disassembly = "LDR{}{} R{}, [R{}".format("" if sizeaccess == 4 else "B", "" if cond == 'AL' else cond, misc['rd'], misc['base'])
                if misc['pre']:
                    description += descoffset
                    description += "<li>Lit {} octets à partir de l'adresse obtenue (pré-incrément) et stocke le résultat dans {} (LDR)</li>\n".format(sizeaccess, _regSuffixWithBank(misc['rd']))
                else:
                    description += "<li>Lit {} octets à partir de l'adresse de base et stocke le résultat dans {} (LDR)</li>\n".format(sizeaccess, _regSuffixWithBank(misc['rd']))
                    description += descoffset
                for addrmem in range(realAddr, realAddr+sizeaccess):
                    highlightread.append("MEM_{:X}".format(addrmem))
                highlightwrite.extend(_registerWithCurrentBank(misc['rd']))
            else:       # STR
                disassembly = "STR{}{} R{}, [R{}".format("" if sizeaccess == 4 else "B", "" if cond == 'AL' else cond, misc['rd'], misc['base'])
                if misc['pre']:
                    description += descoffset
                    description += "<li>Copie la valeur du registre {} dans la mémoire, à l'adresse obtenue à l'étape précédente (pré-incrément), sur {} octets (STR)</li>\n".format(_regSuffixWithBank(misc['rd']), sizeaccess)
                else:
                    description += "<li>Copie la valeur du registre {} dans la mémoire, à l'adresse de base, sur {} octets (STR)</li>\n".format(_regSuffixWithBank(misc['rd']), sizeaccess)
                    description += descoffset

                for addrmem in range(realAddr, realAddr+sizeaccess):
                    highlightwrite.append("MEM_{:X}".format(addrmem))
                highlightread.extend(_registerWithCurrentBank(misc['rd']))

            if misc['pre']:
                if misc['imm']:
                    if misc['offset'] == 0:
                        disassembly += "]"
                    else:
                        disassembly += ", {}]".format(hex(misc['sign'] * misc['offset']))
                else:
                    disassembly += ", R{}".format(misc['offset'][0])
                    disassembly += _shiftToInstruction(misc['offset'][1]) + "]"
            elif misc['offset'] != 0:
                # Post (a post-incrementation of 0 is useless)
                disassembly += "]"
                if misc['imm']:
                    disassembly += " {}".format(hex(misc['sign'] * misc['offset']))
                else:
                    disassembly += " R{}".format(misc['offset'][0])
                    disassembly += _shiftToInstruction(misc['offset'][1])
            else:
                # Weird case, would happen if we combine post-incrementation and immediate offset of 0
                disassembly += "]"

            if misc['writeback']:
                highlightwrite.extend(_registerWithCurrentBank(misc['base']))
                description += "<li>Écrit l'adresse effective dans le registre de base {} (mode writeback)</li>\n".format(_regSuffixWithBank(misc['base']))
                if misc['pre']:
                    disassembly += "!"

        elif t == InstrType.multiplememop:
            if misc['mode'] == 'LDR':
                disassembly = "POP" if misc['base'] == 13 and misc['writeback'] else "LDM"
            else:
                disassembly = "PUSH" if misc['base'] == 13 and misc['writeback'] else "STM"

            if disassembly not in ("PUSH", "POP"):
                if misc['pre']:
                    disassembly += "IB" if misc['sign'] > 0 else "DB"
                else:
                    disassembly += "IA" if misc['sign'] > 0 else "DA"

            if cond != 'AL':
                disassembly += cond

            # TODO : show the affected memory areas

            if disassembly[:3] == 'POP':
                description += "<li>Lit la valeur de SP</li>\n"
                description += "<li>Pour chaque registre de la liste suivante, stocke la valeur contenue à l'adresse pointée par SP dans le registre, puis incrémente SP de 4.</li>\n"
            elif disassembly[:4] == 'PUSH':
                description += "<li>Lit la valeur de SP</li>\n"
                description += "<li>Pour chaque registre de la liste suivante, décrémente SP de 4, puis stocke la valeur du registre à l'adresse pointée par SP.</li>\n"
            elif misc['mode'] == 'LDR':
                description += "<li>Lit la valeur de {}</li>\n".format(_regSuffixWithBank(misc['base']))
            else:
                description += "<li>Lit la valeur de {}</li>\n".format(_regSuffixWithBank(misc['base']))

            if disassembly[:3] not in ("PUS", "POP"):
                disassembly += " R{}{},".format(misc['base'], "!" if misc['writeback'] else "")

            listregstxt = " {"
            beginReg, currentReg = None, None
            for reg in regs:
                if beginReg is None:
                    beginReg = reg
                elif reg != currentReg+1:
                    listregstxt += "R{}".format(beginReg)
                    if currentReg == beginReg:
                        listregstxt += ", "
                    elif currentReg - beginReg == 1:
                        listregstxt += ", R{}, ".format(currentReg)
                    else:
                        listregstxt += "-R{}, ".format(currentReg)
                    beginReg = reg
                currentReg = reg

            if currentReg is None:
                # No register (the last 16 bits are all zeros)
                listregstxt = ""
            else:
                listregstxt += "R{}".format(beginReg)
                if currentReg - beginReg == 1:
                    listregstxt += ", R{}".format(currentReg)
                elif currentReg != beginReg:
                    listregstxt += "-R{}".format(currentReg)
                listregstxt += "}"

            disassembly += listregstxt
            description += "<li>{}</li>\n".format(listregstxt)
            if misc['sbit']:
                disassembly += "^"
                description += "<li>Copie du SPSR courant dans le CPSR</li>\n"


        elif t == InstrType.psrtransfer:
            disassembly = misc['opcode']
            if cond != 'AL':
                disassembly += cond
            if misc['write']:
                disassembly += " SPSR" if misc['usespsr'] else " CPSR"
                if misc['flagsOnly']:
                    disassembly += "_flg"
                    if misc['imm']:
                        valToSet = misc['op2'][0]
                        if misc['op2'][1][2] != 0:
                            _, valToSet = self._shiftVal(valToSet, misc['op2'][1])
                            description += "<li>Écrit la constante {} dans {}</li>\n".format(valToSet, "SPSR" if misc['usespsr'] else "CPSR")
                            disassembly += ", #{}".format(hex(valToSet))
                    else:
                        disassembly += ", R{}".format(misc['op2'][0])
                        highlightread.extend(_registerWithCurrentBank(misc['op2'][0]))
                        description += "<li>Lit la valeur de R{}</li>\n".format(misc['op2'][0])
                        description += "<li>Écrit les 4 bits les plus significatifs de cette valeur (qui correspondent aux drapeaux) dans {}</li>\n".format("SPSR" if misc['usespsr'] else "CPSR")
                else:
                    description += "<li>Lit la valeur de {}</li>\n".format(_regSuffixWithBank(misc['op2'][0]))
                    description += "<li>Écrit cette valeur dans {}</li>\n".format("SPSR" if misc['usespsr'] else "CPSR")
                    disassembly += ", R{}".format(misc['op2'][0])
            else:       # Read
                disassembly += " R{}, {}".format(misc['rd'], "SPSR" if misc['usespsr'] else "CPSR")
                highlightwrite.extend(_registerWithCurrentBank(misc['rd']))
                description += "<li>Lit la valeur de {}</li>\n".format("SPSR" if misc['usespsr'] else "CPSR")
                description += "<li>Écrit le résultat dans {}</li>\n".format(_regSuffixWithBank(misc['rd']))

        elif t == InstrType.multiply:
            op1, op2 = misc['operandsmul']
            destrd = misc['rd']
            if misc['accumulate']:
                # MLA
                disassembly = "MLA"
                description += "<li>Effectue une multiplication suivie d'une addition (A*B+C) entre :\n"
                description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(_regSuffixWithBank(op1))
                description += "<li>Le registre {}</li>\n".format(_regSuffixWithBank(op2))
                description += "<li>Le registre {}</li></ol>\n".format(_regSuffixWithBank(misc['operandadd']))
                if misc['setflags']:
                    disassembly += "S"
                    description += "<li>Met à jour les drapeaux de l'ALU en fonction du résultat de l'opération</li>\n"
                disassembly += " R{}, R{}, R{}, R{} ".format(destrd, op1, op2, misc['operandadd'])
                highlightread.extend(_registerWithCurrentBank(op1))
                highlightread.extend(_registerWithCurrentBank(op2))
                highlightread.extend(_registerWithCurrentBank(misc['operandadd']))
            else:
                # MUL
                disassembly = "MUL"
                description += "<li>Effectue une multiplication (A*B) entre :\n"
                description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(_regSuffixWithBank(op1))
                description += "<li>Le registre {}</li></ol>\n".format(_regSuffixWithBank(op2))
                if misc['setflags']:
                    disassembly += "S"
                    description += "<li>Met à jour les drapeaux de l'ALU en fonction du résultat de l'opération</li>\n"
                disassembly += " R{}, R{}, R{} ".format(destrd, op1, op2)
                highlightread.extend(_registerWithCurrentBank(op1))
                highlightread.extend(_registerWithCurrentBank(op2))

            description += "<li>Écrit le résultat dans R{}</li>".format(destrd)
            highlightwrite.extend(_registerWithCurrentBank(destrd))

            if misc['setflags']:
                for flag in ('c', 'z', 'n'):
                    highlightwrite.append(flag)


        elif t == InstrType.dataop:
            # Get first operand value
            workingFlags = {}
            modifiedFlags = set()
            disassembly = misc['opcode']
            if cond != 'AL':
                disassembly += cond
            if misc['setflags'] and misc['opcode'] not in ("TST", "TEQ", "CMP", "CMN"):
                disassembly += "S"

            op1 = self.regs[misc['rn']].get()
            if misc['opcode'] not in ("MOV", "MVN"):
                highlightread.extend(_registerWithCurrentBank(misc['rn']))

            op2desc = ""
            op2dis = ""
            # Get second operand value
            if misc['imm']:
                op2 = misc['op2'][0]
                if misc['op2'][1][2] != 0:
                    carry, op2 = self._shiftVal(op2, misc['op2'][1])
                    if misc['op2'][1][0] != "LSL" or misc['op2'][1][2] > 0 or misc['op2'][1][1] == "reg":
                        modifiedFlags.add('C')
                op2desc = "La constante {}".format(op2)
                op2dis = "#{}".format(hex(op2))
            else:
                op2 = self.regs[misc['op2'][0]].get()
                highlightread.extend(_registerWithCurrentBank(misc['op2'][0]))
                if misc['op2'][0] == 15 and getSetting("PCspecialbehavior"):
                    op2 += 4    # Special case for PC where we use PC+12 instead of PC+8 (see 4.5.5 of ARM Instr. set)
                carry, op2 = self._shiftVal(op2, misc['op2'][1])
                if misc['op2'][1][0] != "LSL" or misc['op2'][1][2] > 0 or misc['op2'][1][1] == "reg":
                    modifiedFlags.add('C')
                shiftDesc = _shiftToDescription(misc['op2'][1])
                shiftinstr = _shiftToInstruction(misc['op2'][1])
                op2desc = "Le registre {} {}".format(_regSuffixWithBank(misc['op2'][0]), shiftDesc)
                op2dis = "R{}{}".format(misc['op2'][0], shiftinstr)
                if misc['op2'][1][1] == 'reg':
                    highlightread.extend(_registerWithCurrentBank(misc['op2'][1][2]))

            # Get destination register and write the result
            destrd = misc['rd']

            if misc['opcode'] in ("AND", "TST"):
                # These instructions do not affect the V flag (ARM Instr. set, 4.5.1)
                # However, C flag "is set to the carry out from the barrel shifter [if the shift is not LSL #0]" (4.5.1)
                # this was already done when we called _shiftVal
                description += "<li>Effectue une opération ET entre:\n"
            elif misc['opcode'] in ("EOR", "TEQ"):
                # These instructions do not affect the C and V flags (ARM Instr. set, 4.5.1)
                description += "<li>Effectue une opération OU EXCLUSIF (XOR) entre:\n"
            elif misc['opcode'] in ("SUB", "CMP"):
                modifiedFlags.add('C')
                modifiedFlags.add('V')
                description += "<li>Effectue une soustraction (A-B) entre:\n"
                if misc['opcode'] == "SUB" and destrd == 15:
                    # We change PC, we show it in the editor
                    nextline = self.regs[misc['rn']].get() - op2
            elif misc['opcode'] == "RSB":
                modifiedFlags.add('C')
                modifiedFlags.add('V')
                description += "<li>Effectue une soustraction inverse (B-A) entre:\n"
            elif misc['opcode'] in ("ADD", "CMN"):
                modifiedFlags.add('C')
                modifiedFlags.add('V')
                description += "<li>Effectue une addition (A+B) entre:\n"
                if misc['opcode'] == "ADD" and destrd == 15:
                    # We change PC, we show it in the editor
                    nextline = self.regs[misc['rn']].get() + op2
            elif misc['opcode'] == "ADC":
                modifiedFlags.add('C')
                modifiedFlags.add('V')
                description += "<li>Effectue une addition avec retenue (A+B+carry) entre:\n"
            elif misc['opcode'] == "SBC":
                modifiedFlags.add('C')
                modifiedFlags.add('V')
                description += "<li>Effectue une soustraction avec emprunt (A-B+carry) entre:\n"
            elif misc['opcode'] == "RSC":
                modifiedFlags.add('C')
                modifiedFlags.add('V')
                description += "<li>Effectue une soustraction inverse avec emprunt (B-A+carry) entre:\n"
            elif misc['opcode'] == "ORR":
                description += "<li>Effectue une opération OU entre:\n"
            elif misc['opcode'] == "MOV":
                description += "<li>Lit la valeur de :\n"
                if destrd == 15:
                    # We change PC, we show it in the editor
                    nextline = op2
            elif misc['opcode'] == "BIC":
                description += "<li>Effectue une opération ET NON entre:\n"
            elif misc['opcode'] == "MVN":
                description += "<li>Effectue une opération NOT sur :\n"
                if destrd == 15:
                    # We change PC, we show it in the editor
                    nextline = ~op2
            else:
                assert False, "Bad data opcode : " + misc['opcode']

            if misc['opcode'] in ("MOV", "MVN"):
                description += "<ol type=\"A\"><li>{}</li></ol>\n".format(op2desc)
                disassembly += " R{}, ".format(destrd)
            elif misc['opcode'] in ("TST", "TEQ", "CMP", "CMN"):
                description += "<ol type=\"A\"><li>Le registre {}</li><li>{}</li></ol>\n".format(_regSuffixWithBank(misc['rn']), op2desc)
                disassembly += " R{}, ".format(misc['rn'])
            else:
                description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(_regSuffixWithBank(misc['rn']))
                description += "<li>{}</li></ol>\n".format(op2desc)
                disassembly += " R{}, R{}, ".format(destrd, misc['rn'])
            disassembly += op2dis

            description += "</li>\n"
            modifiedFlags.add('Z')
            modifiedFlags.add('N')

            if misc['setflags']:
                if destrd == 15:
                    description += "<li>Copie le SPSR courant dans CPSR</li>\n"
                else:
                    for flag in modifiedFlags:
                        highlightwrite.append(flag.lower())
                    description += "<li>Met à jour les drapeaux de l'ALU en fonction du résultat de l'opération</li>\n"
            if misc['opcode'] not in ("TST", "TEQ", "CMP", "CMN"):
                description += "<li>Écrit le résultat dans {}</li>".format(_regSuffixWithBank(destrd))
                highlightwrite.extend(_registerWithCurrentBank(destrd))

        if t != InstrType.undefined:
            description += "</ol>"

        dis = '<div id="disassembly_instruction">{}</div>\n<div id="disassembly_description">{}</div>\n'.format(disassembly, description)
        #if t == InstrType.branch or instrWillExecute:
        if nextline != -1:
            self.disassemblyInfo = ["highlightread", highlightread], ["highlightwrite", highlightwrite], ["nextline", nextline], ["disassembly", dis]
        else:
            self.disassemblyInfo = ["highlightread", highlightread], ["highlightwrite", highlightwrite], ["disassembly", dis]


    def execInstr(self):
        """
        Execute one instruction
        :param addr: Address of the instruction in memory
        :return: a boolean indicating if PC was modified by the current instruction
        This function may throw a SimulatorError exception if there's an error, or a Breakpoint exception,
        in which case it is not an error but rather a Breakpoint reached.
        """

        # Decode it
        t, regs, cond, misc = self.decodedInstr
        workingFlags = {}
        pcchanged = False

        if t == InstrType.undefined:
            # Invalid instruction, we report it
            try:
                self.sysHandle.throw(BkptInfo("assert", None, (self.addr2line[self.regs[15].get()-self.pcoffset][-1]-1,
                                                           "Erreur : le bytecode ne correspond à aucune instruction valide!")))
            except IndexError:
                self.sysHandle.throw(BkptInfo("pc", None, ("Erreur : la valeur de PC ({}) est invalide (ce doit être un multiple de 4)"
                                                           ", et le bytecode pointé ne correspond à aucune instruction valide!".format(hex(self.regs[15].get())))))
            return False


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
                self.callStack.append(self.regs[15].get() - self.pcoffset)
            if misc['mode'] == 'imm':
                self.regs[15].set(self.regs[15].get() + misc['offset'])
            else:   # BX
                self.regs[15].set(self.regs[misc['offset']].get())
                self.stepCondition -= 1         # We are returning from a function, we log it (useful for stepForward and stepOut)
                if len(self.callStack) > 0:
                    self.callStack.pop()
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
                res = struct.unpack("<B" if misc['byte'] else "<I", m)[0]
                self.regs[misc['rd']].set(res)
                if misc['rd'] == 15:
                    pcchanged = True
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
                    if m is None:       # No such address in the mapped memory, we cannot continue
                        return False
                    val = struct.unpack("<I", m)[0]
                    self.regs[reg].set(val)
                    baseAddr += misc['sign'] * 4
                if misc['sbit'] and 15 in regs:
                    # "If the instruction is a LDM then SPSR_<mode> is transferred to CPSR at the same time as R15 is loaded."
                    self.regs.getCPSR().set(self.regs.getSPSR().get())
            else:   # STR
                for reg in regs[::misc['sign']]:
                    val = self.regs[reg].get()
                    if reg == 15:
                        val += 4            # PC+12 when PC is in an STM instruction (see 4.11.1 of the ARM instruction set manual)
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
                if misc['usespsr'] and self.regs.getSPSR() is None:
                    # Check if SPSR exists (we are not in user mode)
                    self.sysHandle.throw(
                        BkptInfo("assert", None, (self.addr2line[self.regs[15].get() - self.pcoffset][-1] - 1,
                                                  "Erreur : écriture de SPSR en mode 'User' (ce mode ne possede pas de registre SPSR)")))
                    return False
                if misc['flagsOnly']:
                    if misc['imm']:
                        valToSet = misc['op2'][0]
                        if misc['op2'][1][2] != 0:
                            _, valToSet = self._shiftVal(valToSet, misc['op2'][1])
                    else:
                        valToSet = self.regs[misc['op2'][0]].get() & 0xF0000000   # We only keep the condition flag bits
                    if misc['usespsr']:
                        valToSet |= self.regs.getSPSR().get() & 0x0FFFFFFF
                    else:
                        valToSet |= self.regs.getCPSR().get() & 0x0FFFFFFF
                else:
                    valToSet = self.regs[misc['op2'][0]].get()

                if (valToSet & 0x1F) not in self.regs.getCPSR().bits2mode:
                    self.sysHandle.throw(
                        BkptInfo("assert", None, (self.addr2line[self.regs[15].get() - self.pcoffset][-1] - 1,
                                                  "Erreur : les bits ({:05b}) du mode du {} ne correspondent à aucun mode valide!".format(valToSet & 0x1F, "SPSR" if misc['usespsr'] else "CPSR"))))
                    return False

                if misc['usespsr']:
                    self.regs.getSPSR().set(valToSet)
                else:
                    if not getSetting("allowuserswitchmode") and self.regs.getSPSR() is None and self.regs.getCPSR().get() & 0x1F != valToSet & 0x1F:
                        self.sysHandle.throw(
                            BkptInfo("assert", None, (self.addr2line[self.regs[15].get() - self.pcoffset][-1] - 1,
                                                      "Erreur : tentative de changer le mode du processeur à partir d'un mode non privilégié!")))
                        return False
                    self.regs.getCPSR().set(valToSet)
                    self.regs.setCurrentBankFromMode(valToSet & 0b11111)
            else:       # Read
                if misc['usespsr'] and self.regs.getSPSR() is None:
                    # Check if SPSR exists (we are not in user mode)
                    self.sysHandle.throw(
                        BkptInfo("assert", None, (self.addr2line[self.regs[15].get() - self.pcoffset][-1] - 1,
                                                  "Erreur : lecture de SPSR en mode 'User' (ce mode ne possede pas de registre SPSR)")))
                else:
                    self.regs[misc['rd']].set(self.regs.getSPSR().get() if misc['usespsr'] else self.regs.getCPSR().get())

        elif t == InstrType.multiply:
            op1 = self.regs[misc['operandsmul'][0]].get()
            op2 = self.regs[misc['operandsmul'][1]].get()
            destrd = misc['rd']
            if misc['accumulate']:
                # MLA
                res = op1 * op2 + self.regs[misc['operandadd']].get()
            else:
                # MUL
                res = op1 * op2

            self.regs[destrd].set(res & 0xFFFFFFFF)

            # Z and V are set, C is set to "meaningless value" (see ARM spec 4.7.2), V is unaffected
            workingFlags['Z'] = res == 0
            workingFlags['N'] = res & 0x80000000  # "N flag will be set to the value of bit 31 of the result" (4.5.1)
            workingFlags['C'] = 0       # I suppose "0" can be qualified as a meaningless value...

            if misc['setflags']:
                for flag in workingFlags:
                    self.flags[flag] = workingFlags[flag]

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
                if misc['op2'][0] == 15 and misc['op2'][1][1] == "reg" and getSetting("PCspecialbehavior"):
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
                # For a subtraction, including the comparison instruction CMP, C is set to 0
                # if the subtraction produced a borrow (that is, an unsigned underflow), and to 1 otherwise.
                # http://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.dui0801a/CIADCDHH.html
                res, workingFlags['C'], workingFlags['V'] = self._addWithCarry(op1, ~op2, 1)
            elif misc['opcode'] == "RSB":
                res, workingFlags['C'], workingFlags['V'] = self._addWithCarry(~op1, op2, 1)
            elif misc['opcode'] in ("ADD", "CMN"):
                res, workingFlags['C'], workingFlags['V'] = self._addWithCarry(op1, op2, 0)
            elif misc['opcode'] == "ADC":
                res, workingFlags['C'], workingFlags['V'] = self._addWithCarry(op1, op2, int(self.flags['C']))
            elif misc['opcode'] == "SBC":
                res, workingFlags['C'], workingFlags['V'] = self._addWithCarry(op1, ~op2, int(self.flags['C']))
            elif misc['opcode'] == "RSC":
                res, workingFlags['C'], workingFlags['V'] = self._addWithCarry(~op1, op2, int(self.flags['C']))
            elif misc['opcode'] == "ORR":
                res = op1 | op2
            elif misc['opcode'] == "MOV":
                res = op2
            elif misc['opcode'] == "BIC":
                res = op1 & ~op2     # Bit clear?
            elif misc['opcode'] == "MVN":
                res = ~op2
            else:
                BkptInfo("assert", None, (self.addr2line[self.regs[15].get() - self.pcoffset][-1] - 1,
                                          "Mnémonique invalide : {}".format(misc['opcode'])))
                return pcchanged

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
                        BkptInfo("assert", None, (self.addr2line[self.regs[15].get() - self.pcoffset][-1] - 1,
                                                  "L'utilisation de PC comme registre de destination en combinaison avec la mise a jour des drapeaux est interdite en mode User!"))
                        return pcchanged
                    self.regs.getCPSR().set(self.regs.getSPSR().get())          # Put back the saved SPSR in CPSR
                    self.regs.setCurrentBankFromMode(self.regs.getCPSR().get() & 0x1F)
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

        if self.decodedInstr is None:
            # The current instruction has not be retrieved or decoded (because it was an illegal access)
            return

        # We clear an eventual breakpoint
        self.sysHandle.clearBreakpoint()

        keeppc = self.regs[15].get() - self.pcoffset

        # The instruction should have been fetched by the last instruction
        currentCallStackLen = len(self.callStack)
        pcmodified = self.execInstr()
        if pcmodified:
            self.regs[15].set(self.regs[15].get() + self.pcoffset)
        else:
            self.regs[15].set(self.regs[15].get() + 4)        # PC = PC + 4

        newpc = self.regs[15].get() - self.pcoffset

        if keeppc in self.assertionCkpts and not pcmodified:
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

        # We fetch and decode the next instruction
        self.fetchAndDecode()

        # Question : if we hit a breakpoint for the _next_ instruction, should we enter the interrupt anyway?
        # Did we hit a breakpoint?
        # A breakpoint always stop the simulator
        if self.sysHandle.breakpointTrigged:
            self.stepMode = None


