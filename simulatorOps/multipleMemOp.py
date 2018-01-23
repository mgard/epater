import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque
from functools import reduce

import simulatorOps.utils as utils
from simulatorOps.abstractOp import AbstractOp, ExecutionException

class MultipleMemOp(AbstractOp):
    saveStateKeys = frozenset(("condition", 
                                "mode", "pre", "sign", "sbit", "writeback",
                                "basereg", "regbitmap", "reglist"))

    def __init__(self):
        super().__init__()
        self._type = utils.InstrType.multiplememop

    def decode(self):
        instrInt = self.instrInt
        if not (utils.checkMask(instrInt, (27,), (26, 25))):
            raise ExecutionException("masque de décodage invalide pour une instruction de type MULTIPLEMEM", 
                                        internalError=True)

        # Retrieve the condition field
        self._decodeCondition()
        
        self.pre = bool(instrInt & (1 << 24))
        self.sign = 1 if instrInt & (1 << 23) else -1
        self.sbit = bool(instrInt & (1 << 22))
        self.writeback = bool(instrInt & (1 << 21))
        self.mode = "LDR" if instrInt & (1 << 20) else "STR"

        self.basereg = (instrInt >> 16) & 0xF
        self.regbitmap = instrInt & 0xFFFF
        reglist = []
        for i in range(16):
            if self.regbitmap & (1 << i):
                reglist.append(i)
        self.reglist = tuple(reglist)

    def explain(self, simulatorContext):
        self.resetAccessStates()
        bank = simulatorContext.regs.mode
        simulatorContext.regs.deactivateBreakpoints()
        
        disassembly = ""
        description = "<ol>\n"
        disCond, descCond = self._explainCondition()
        description += descCond

        if self.mode == 'LDR':
            disassembly = "POP" if self.basereg == 13 and self.writeback else "LDM"
        else:
            disassembly = "PUSH" if self.basereg == 13 and self.writeback else "STM"

        if disassembly not in ("PUSH", "POP"):
            if self.pre:
                disassembly += "IB" if self.sign > 0 else "DB"
            else:
                disassembly += "IA" if self.sign > 0 else "DA"

        disassembly += disCond

        # See the explanations in execute() for this line
        transferToUserBank = bank != "User" and self.sbit and (self.mode == "STR" or 15 not in self.reglist)
        bankToUse = "User" if transferToUserBank else bank

        if disassembly[:3] == 'POP':
            description += "<li>Lit la valeur de SP</li>\n"
            description += "<li>Pour chaque registre de la liste suivante, stocke la valeur contenue à l'adresse pointée par SP dans le registre, puis incrémente SP de 4.</li>\n"
        elif disassembly[:4] == 'PUSH':
            description += "<li>Lit la valeur de SP</li>\n"
            description += "<li>Pour chaque registre de la liste suivante, décrémente SP de 4, puis stocke la valeur du registre à l'adresse pointée par SP.</li>\n"
        else:
            description += "<li>Lit la valeur de {}</li>\n".format(utils.regSuffixWithBank(self.basereg, bank))

        if disassembly[:3] not in ("PUS", "POP"):
            disassembly += " R{}{},".format(self.basereg, "!" if self.writeback else "")

        listregstxt = " {"
        beginReg, currentReg = None, None
        for reg in self.reglist:
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
        if self.sbit:
            disassembly += "^"
            if self.mode == "LDR" and 15 in self.reglist:
                description += "<li>Copie du SPSR courant dans le CPSR</li>\n"

        self._readregs |= utils.registerWithCurrentBank(self.basereg, bank)
        if self.mode == "LDR":
            self._readregs |= reduce(operator.or_, [utils.registerWithCurrentBank(reg, bankToUse) for reg in self.reglist])
        else:
            self._writeregs |= reduce(operator.or_, [utils.registerWithCurrentBank(reg, bankToUse) for reg in self.reglist])

        # TODO : update _readmem and _writemem
        # (show the affected memory areas)

        description += "</ol>"
        simulatorContext.regs.reactivateBreakpoints()
        return disassembly, description
    
    def execute(self, simulatorContext):
        if not self._checkCondition(simulatorContext.regs):
            # Nothing to do, instruction not executed
            return

        # "The lowest-numbereing register is stored to the lowest memory address, through the
        # highest-numbered register to the highest memory address"
        baseAddr = simulatorContext.regs[self.basereg]
        if self.pre:
            baseAddr += self.sign * 4

        currentbank = simulatorContext.regs.mode
        # If R15 not in list and S bit set (ARM Instruction Set Manual, 4.11.4)
        # "For both LDM and STM instructions, the User bank registers are transferred rather than the register
        #  bank corresponding to the current mode. This is useful for saving the user state on process switches.
        #  Base write-back should not be used when this mechanism is employed."
        transferToUserBank = currentbank != "User" and self.sbit and (self.mode == "STR" or 15 not in self.reglist)

        if self.mode == 'LDR':
            for reg in self.reglist[::self.sign]:
                m = simulatorContext.mem.get(baseAddr, size=4)
                if m is None:       # No such address in the mapped memory, we cannot continue
                    return False
                val = struct.unpack("<I", m)[0]
                if transferToUserBank:
                    simulatorContext.regs.setRegister("User", reg, val)
                else:
                    simulatorContext.regs[reg] = val
                baseAddr += self.sign * 4
            if self.sbit and simulatorContext.PC in self.reglist:
                # "If the instruction is a LDM then SPSR_<mode> is transferred to CPSR at the same time as R15 is loaded."
                simulatorContext.regs.CPSR = simulatorContext.regs.SPSR
        else:   # STR
            for reg in self.reglist[::self.sign]:
                val = simulatorContext.regs.getRegister("User", reg) if transferToUserBank else simulatorContext.regs[reg]
                if reg == simulatorContext.PC:
                    val += 4            # PC+12 when PC is in an STM instruction (see 4.11.1 of the ARM instruction set manual)
                simulatorContext.mem.set(baseAddr, val, size=4)
                baseAddr += self.sign * 4
        if self.pre:
            baseAddr -= self.sign * 4        # If we are in pre-increment mode, we remove the last increment

        if self.writeback:
            # Technically, it will break if we use a different bank (e.g. the S bit is set), but the ARM spec
            # explicitely says that "Base write-back should not be used when this mechanism (the S bit) is employed".
            # Maybe we could output an explicit error if this is the case?
            simulatorContext.regs[self.basereg] = baseAddr

            # TODO Handle special case of the inclusion of base register in the register list (see ARM manual 4.11.6)

