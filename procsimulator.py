import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple

from settings import getSetting
from instruction import BytecodeToInstrInfos, InstrType


class SimulatorError(Exception):
    def __init__(self, desc):
        self.desc = desc
    def __str__(self):
        return self.desc


BkptInfo = namedtuple("BkptInfo", ['source', 'mode', 'infos'])
class BreakPointHandler:
    def __init__(self):
        self.breakpointTrigged = None
        self.breakpointInfo = None
        self.reset()

    def reset(self):
        self.breakpointTrigged = False
        self.breakpointInfo = None

    def throw(self, infos):
        self.breakpointTrigged = True
        self.breakpointInfo = infos


class Register:

    def __init__(self, n, breakpointHandler, val=0, altname=None):
        self.id = n
        self.val = val
        self.bkpt = breakpointHandler
        self.altname = altname
        self.history = []
        self.breakpoint = 0

    @property
    def name(self):
        return "R{}".format(self.id)

    def get(self, mayTriggerBkpt=True):
        if mayTriggerBkpt and self.breakpoint & 4:
            self.bkpt.throw(BkptInfo("register", 4, self.id))
        return self.val

    def set(self, val, mayTriggerBkpt=True):
        val &= 0xFFFFFFFF
        if mayTriggerBkpt and self.breakpoint & 2:
            self.bkpt.throw(BkptInfo("register", 2, self.id))
        self.history.append(val)
        self.val = val


class ControlRegister:
    flag2index = {'N': 31, 'Z': 30, 'C': 29, 'V': 28, 'I': 7, 'F': 6}
    index2flag = {v:k for k,v in flag2index.items()}
    mode2bits = {'User': 16, 'FIQ': 17, 'IRQ': 18, 'SVC': 19}       # Other modes are not supported
    bits2mode = {v:k for k,v in mode2bits.items()}

    def __init__(self, name, breakpointHandler):
        self.regname = name
        self.bkpt = breakpointHandler
        self.val = 0x100
        self.breakpoints = {flag:0 for flag in self.flag2index.keys()}

    @property
    def name(self):
        return self.regname

    def setMode(self, mode):
        if mode not in self.mode2bits:
            raise KeyError
        self.val |= self.mode2bits[mode]
        self.val &= 0xFFFFFFE0 + self.mode2bits[mode]

    def getMode(self):
        return self.bits2mode[self.val & 0x1F]

    def __getitem__(self, flag):
        flag = flag.upper()
        if flag not in self.flag2index:      # Thumb and Jazelle mode are not implemented
            raise KeyError

        if self.breakpoints[flag] & 4:
            self.bkpt.throw(BkptInfo("flag", 4, flag))

        return bool((self.val >> self.flag2index[flag]) & 0x1)

    def __setitem__(self, flag, value):
        flag = flag.upper()
        if flag not in self.flag2index:
            raise KeyError

        if self.breakpoints[flag] & 2:
            self.bkpt.throw(BkptInfo("flag", 2, flag))

        if value:   # We set the flag
            self.val |= 1 << self.flag2index[flag]
        else:       # We clear the flag
            self.val &= 0xFFFFFFFF - (1 << self.flag2index[flag])

    def get(self):
        # Return the content of the PSR as an integer
        return self.val

    def getAllFlags(self):
        # This function never triggers a breakpoint
        return {flag: bool((self.val >> self.flag2index[flag]) & 0x1) for flag in self.flag2index.keys()}

    def set(self, val):
        # Be careful with this method, many values are illegal
        # Use setMode and __setitem__ whenever possible!
        # Mostly use for internal purposes like saving the CPSR in SPSR when an interrupt arises
        self.val = val


class BankedRegisters:

    def __init__(self, breakpointHandler):
        # Create regular registers
        self.banks = {}
        regs = [Register(i, breakpointHandler) for i in range(16)]
        regs[13].altname = "SP"
        regs[14].altname = "LR"
        regs[15].altname = "PC"
        # We add the flags
        # No SPSR in user mode
        flags = (ControlRegister("CPSR", breakpointHandler), None)
        self.banks['User'] = (regs, flags)

        # Create FIQ registers
        regsFIQ = regs[:8]          # R0-R7 are shared
        regsFIQ.extend(Register(i, breakpointHandler) for i in range(8, 15))        # R8-R14 are exclusive
        regsFIQ.append(regs[15])    # PC is shared
        flagsFIQ = (flags[0], ControlRegister("SPSR_fiq", breakpointHandler))
        self.banks['FIQ'] = (regsFIQ, flagsFIQ)

        # Create IRQ registers
        regsIRQ = regs[:13]         # R0-R12 are shared
        regsIRQ.extend(Register(i, breakpointHandler) for i in range(13, 15))        # R13-R14 are exclusive
        regsIRQ.append(regs[15])    # PC is shared
        flagsIRQ = (flags[0], ControlRegister("SPSR_irq", breakpointHandler))
        self.banks['IRQ'] = (regsIRQ, flagsIRQ)

        # Create SVC registers (used with software interrupts)
        regsSVC = regs[:13]  # R0-R12 are shared
        regsSVC.extend(Register(i, breakpointHandler) for i in range(13, 15))  # R13-R14 are exclusive
        regsSVC.append(regs[15])  # PC is shared
        flagsSVC = (flags[0], ControlRegister("SPSR_svc", breakpointHandler))
        self.banks['SVC'] = (regsSVC, flagsSVC)

        # By default, we are in user mode
        self.setCurrentBank("User")

    def setCurrentBank(self, bankname):
        self.currentBank = bankname

    def __getitem__(self, item):
        if not isinstance(item, int) or item < 0 or item > 15:
            raise IndexError
        return self.banks[self.currentBank][0][item]

    def getCPSR(self):
        return self.banks[self.currentBank][1][0]

    def getSPSR(self):
        return self.banks[self.currentBank][1][1]

    def getAllRegisters(self):
        # Helper function to get all registers from all banks at once
        # The result is returned as a dictionary of dictionary
        return {bname: {bank[0][ridx].name: bank[0][ridx].get(mayTriggerBkpt=False) for ridx in range(len(bank[0]))} for bname, bank in self.banks.items()}


class Memory:

    def __init__(self, memcontent, breakpointHandler, initval=0):
        self.size = sum(len(b) for b in memcontent)
        self.initval = initval
        self.history = []
        self.bkpt = breakpointHandler
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

    def get(self, addr, size=4, execMode=False):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            self.bkpt.throw(BkptInfo("memory", 8, addr))
            return None

        for offset in range(size):
            if execMode and self.breakpoints[addr+offset] & 1:
                self.bkpt.throw(BkptInfo("memory", 1, addr+offset))
            if self.breakpoints[addr+offset] & 4:
                self.bkpt.throw(BkptInfo("memory", 4, addr+offset))

        sec, offset = resolvedAddr
        return self.data[sec][offset:offset+size]

    def set(self, addr, val, size=4):
        resolvedAddr = self._getRelativeAddr(addr, size)
        if resolvedAddr is None:
            self.bkpt.throw(BkptInfo("memory", 8, addr))
            return

        for offset in range(size):
            if self.breakpoints[addr+offset] & 2:
                self.bkpt.throw(BkptInfo("memory", 2, addr+offset))

        sec, offset = resolvedAddr
        val &= 0xFFFFFFFF
        self.history.append((sec, offset, size, val))
        self.data[sec][offset:offset+size] = val

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

    def setBreakpoint(self, addr, modeOctal):
        self.breakpoints[addr] = modeOctal

    def removeBreakpoint(self, addr):
        self.breakpoints[addr] = 0


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
        self.breakpointHandler = BreakPointHandler()
        self.mem = Memory(memorycontent, self.breakpointHandler)

        self.interruptActive = False
        self.interruptParams = {'b': 0, 'a': 0, 't0': 0, 'type': "FIQ"}       # Interrupt trigged at each a*(t-t0) + b cycles
        self.lastInterruptCycle = -1

        self.regs = BankedRegisters(self.breakpointHandler)

        self.stepMode = None
        self.stepCondition = 0

        self.flags = self.regs.getCPSR()

        self.fetchedInstr = None

    def reset(self):
        self.state = SimState.ready
        self.countCycle = 0
        self.regs[15].set(0)
        # We fetch the first instruction
        self.fetchedInstr = bytes(self.mem.get(self.regs[15].get(), execMode=True))

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

        # We are doing a step into, we always stop
        return True


    def setStepCondition(self, stepMode):
        assert stepMode in ("out", "forward")
        self.stepMode = stepMode
        self.stepCondition = 1


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


    def execInstr(self):
        """
        Execute one instruction
        :param addr: Address of the instruction in memory
        :return:
        This function may throw a SimulatorError exception if there's an error, or a Breakpoint exception,
        in which case it is not an error but rather a Breakpoint reached.
        """

        # Decode it
        t, regs, cond, misc = BytecodeToInstrInfos(self.fetchedInstr)
        workingFlags = {}

        # Check condition
        # Warning : here we check if the condition is NOT met, hence we use the
        # INVERSE of the actual condition
        # See Table 4-2 of ARM7TDMI data sheet as reference of these conditions
        if cond == "EQ" and not self.flags['Z'] or \
            cond == "NE" and self.flags['Z'] or \
            cond == "CS" and not self.flags['C'] or \
            cond == "CC" and self.flags['C'] or \
            cond == "MI" and not self.flags['N'] or \
            cond == "PI" and self.flags['N'] or \
            cond == "VS" and not self.flags['V'] or \
            cond == "VC" and self.flags['V'] or \
            cond == "HI" and (not self.flags['C'] or self.flags['Z']) or \
            cond == "LS" and (self.flags['C'] and not self.flags['Z']) or \
            cond == "GE" and not self.flags['V'] == self.flags['N'] or \
            cond == "LT" and self.flags['V'] == self.flags['N'] or \
            cond == "GT" and (self.flags['Z'] or not self.flags['V'] == self.flags['N']) or \
            cond == "LE" and (not self.flags['Z'] and self.flags['V'] == self.flags['N']):
            # Condition not met, return
            return

        # Execute it
        if t == InstrType.branch:
            if misc['L']:       # Link
                self.regs[14].set(self.regs[15].get()+4)
                self.stepCondition += 1         # We are entering a function, we log it (useful for stepForward and stepOut)
            if misc['mode'] == 'imm':
                print(misc['offset'])
                self.regs[15].set(self.regs[15].get() + misc['offset'] - 4)
            else:   # BX
                self.regs[15].set(self.regs[misc['offset']].get() - 4)
                self.stepCondition -= 1         # We are returning from a function, we log it (useful for stepForward and stepOut)

        elif t == InstrType.memop:
            baseval = self.regs[misc['base']].get()
            addr = baseval
            if misc['imm']:
                addr += misc['sign'] * misc['offset']
            else:
                sval, _ = self._shiftVal(self.regs[misc['offset'][0]].get(), misc['offset'][1])
                addr += misc['sign'] * sval

            realAddr = addr if misc['pre'] else baseval
            if misc['mode'] == 'LDR':
                m = self.mem.get(realAddr, size=1 if misc['byte'] else 4)
                if m is None:       # No such address in the mapped memory, we cannot continue
                    return
                res = struct.unpack("<I", m)[0]
                self.regs[misc['rd']].set(res)
            else:       # STR
                self.mem.set(realAddr, self.regs[misc['rd']].get(), size=1 if misc['byte'] else 4)

            if misc['writeback']:
                self.regs[misc['base']].set(addr)

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
            # Get first operand value
            op1 = self.regs[misc['rn']].get()
            # Get second operand value
            if misc['imm']:
                op2 = misc['op2'][0]
                if misc['op2'][1][2] != 0:
                    _, op2 = self._shiftVal(op2, misc['op2'][1])
            else:
                op2 = self.regs[misc['op2'][0]].get()
                carry, op2 = self._shiftVal(op2, misc['op2'][1])
                workingFlags['C'] = bool(carry)

            # Get destination register and write the result
            destrd = misc['rd']

            if misc['opcode'] in ("AND", "TST"):
                # These instructions do not affect the C and V flags (ARM Instr. set, 4.5.1)
                res = op1 & op2
            elif misc['opcode'] in ("EOR", "TEQ"):
                # These instructions do not affect the C and V flags (ARM Instr. set, 4.5.1)
                res = op1 ^ op2
            elif misc['opcode'] in ("SUB", "CMP"):
                # TODO : update carry and overflow flags
                res = op1 - op2
            elif misc['opcode'] == "RSB":
                # TODO : update carry and overflow flags
                res = op2 - op1
            elif misc['opcode'] in ("ADD", "CMN"):
                res = op1 + op2
                workingFlags['C'] = bool(res & (1 << 32))
                if not bool((op1 & 0x80000000) ^ (op2 & 0x80000000)):
                    workingFlags['V'] = not bool((op1 & 0x80000000) ^ (res & 0x80000000))
            elif misc['opcode'] == "ADC":
                res = op1 + op2 + int(self.flags['C'].get())
                workingFlags['C'] = bool(res & (1 << 32))
                if not bool((op1 & 0x80000000) ^ (op2 & 0x80000000)):
                    workingFlags['V'] = not bool((op1 & 0x80000000) ^ (res & 0x80000000))
            elif misc['opcode'] == "SBC":
                # TODO : update carry and overflow flags
                res = op1 - op2 + int(self.flags['C'].get()) - 1
            elif misc['opcode'] == "RSC":
                # TODO : update carry and overflow flags
                res = op2 - op1 + int(self.flags['C'].get()) - 1
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

            if res == 0:
                workingFlags['Z'] = True
            if res & 0x80000000:
                workingFlags['N'] = True            # "N flag will be set to the value of bit 31 of the result" (4.5.1)

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
                        self.flags[flag].set(workingFlags[flag])
            if misc['opcode'] not in ("TST", "TEQ", "CMP", "CMN"):
                # We actually write the result
                self.regs[destrd].set(res)

    def nextInstr(self):
        # We clear an eventual breakpoint
        self.breakpointHandler.reset()

        if self.interruptActive and (self.lastInterruptCycle == -1 and self.countCycle - self.interruptParams['b'] >= self.interruptParams['t0'] or
                                        self.lastInterruptCycle >= 0 and self.countCycle - self.lastInterruptCycle >= self.interruptParams['a']):
            if (self.interruptParams['type'] == "FIQ" and not self.regs.getCPSR()['F'] or
                    self.interruptParams['type'] == "IRQ" and not self.regs.getCPSR()['I']):        # Is the interrupt masked?
                # Interruption!
                # We enter it (the entry point is 0x18 for IRQ and 0x1C for FIQ)
                self.regs.setCurrentBank(self.interruptParams['type'])                  # Set the register bank
                self.regs.getSPSR().set(self.regs.getCPSR().get())                      # Save the CPSR in the current SPSR
                self.regs.getCPSR().setMode(self.interruptParams['type'])               # Set the interrupt mode in CPSR
                self.regs.getCPSR()[self.interruptParams['type'][0]] = True             # Disable interrupts
                self.regs[14].set(self.regs[15].get() + 8)                              # Save PC in LR (on the FIQ or IRQ bank)
                self.regs[15].set(0x18 if self.interruptParams['type'] == "IRQ" else 0x1C)      # Set PC to enter the interrupt
                self.lastInterruptCycle = self.countCycle

        # The instruction should have been fetched by the last instruction
        self.execInstr()
        self.regs[15].set(self.regs[15].get()+4)        # PC = PC + 4

        # Retrieve instruction from memory
        nextInstrBytes = self.mem.get(self.regs[15].get(), execMode=True)
        if nextInstrBytes is not None:          # We did not make an illegal memory access
            self.fetchedInstr = bytes(nextInstrBytes)

        # Did we hit a breakpoint?
        # A breakpoint always stop the simulator
        if self.breakpointHandler.breakpointTrigged:
            self.stepMode = None

        # One more cycle done!
        self.countCycle += 1

