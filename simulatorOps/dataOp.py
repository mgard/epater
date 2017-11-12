import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import utils
from abstractOp import AbstractOp, ExecutionException

class DataOp(AbstractOp):

    def __init__(self, bytecode):
        super().__init__(bytecode)
        self._type = utils.InstrType.dataop
        self._nextline = -1
        self._modflags = ()

    def decode(self):
        assert utils.checkMask(self.instrInt, (), (27, 26)),
        instrInt = self.instrInt

        # Retrieve condition filed
        if instrInt >> 28 == 15:    # Invalid condition code
            self.decodeError = True
            return
        self.condition = utils.conditionMappingR[instrInt >> 28]

        # Get the opcode
        self.opcodeNum = (instrInt >> 21) & 0xF
        self.opcode = utils.dataOpcodeMappingR[self.opcodeNum]

        # "Immediate" and "set flags"
        self.imm = bool(instrInt & (1 << 25))
        self.modifyFlags = bool(instrInt & (1 << 20))

        self.rd = (instrInt >> 12) & 0xF    # Destination register
        self.rn = (instrInt >> 16) & 0xF    # First operand register

        if self.imm:
            self.shiftedVal = instrInt & 0xFF
            # see 4.5.3 of ARM doc to understand the * 2
            self.shift = utils.shiftInfo(type="ROR", 
                                            immediate=True, 
                                            value=((instrInt >> 8) & 0xF) * 2)
            if self.shift.value != 0:
                # If it is a constant, we shift as we decode
                _, self.shiftedVal = utils.applyShift(self.val, self.shift, False)
        else:
            self.op2reg = instrInt & 0xF
            if instrInt & (1 << 4):
                self.shift = utils.shiftInfo(type=utils.shiftMappingR[(instrInt >> 5) & 0x3],
                                                immediate=False,
                                                value=(instrInt >> 8) & 0xF)
            else:
                self.shift = utils.shiftInfo(type=utils.shiftMappingR[(instrInt >> 5) & 0x3],
                                                immediate=True,
                                                value=(instrInt >> 7) & 0x1F)

    def explain(self, simulatorContext):
        bank = simulatorContext.bank
        modifiedFlags = {'Z', 'N'}
        highlightread, highlightwrite = [], []

        disassembly = self.opcode
        if cond != 'AL':
            disassembly += cond
        if self.modifyFlags and self.opcode not in ("TST", "TEQ", "CMP", "CMN"):
            disassembly += "S"

        op1 = simulatorContext.regs[self.rn].get()
        if self.opcode not in ("MOV", "MVN"):
            highlightread.extend(utils.registerWithCurrentBank(self.rn, bank))

        op2desc = ""
        op2dis = ""
        # Get second operand value
        if self.imm:
            op2 = self.shiftedVal
            op2desc = "La constante {}".format(op2)
            op2dis = "#{}".format(hex(op2))
        else:
            highlightread.extend(utils.registerWithCurrentBank(self.op2reg, bank))
            
            if self.shift.type != "LSL" or self.shift.value > 0 or not self.shift.immediate:
                modifiedFlags.add('C')

            shiftDesc = utils.shiftToDescription(self.shift, bank)
            shiftinstr = utils.shiftToInstruction(self.shift)
            op2desc = "Le registre {} {}".format(utils.regSuffixWithBank(self.shift.value, bank), shiftDesc)
            op2dis = "R{}{}".format(self.op2reg, shiftinstr)
            if not self.shift.immediate:
                highlightread.extend(utils.registerWithCurrentBank(self.shift.value, bank))

        if self.opcode in ("AND", "TST"):
            # These instructions do not affect the V flag (ARM Instr. set, 4.5.1)
            # However, C flag "is set to the carry out from the barrel shifter [if the shift is not LSL #0]" (4.5.1)
            # this was already done when we called _shiftVal
            description += "<li>Effectue une opération ET entre:\n"
        elif self.opcode in ("EOR", "TEQ"):
            # These instructions do not affect the C and V flags (ARM Instr. set, 4.5.1)
            description += "<li>Effectue une opération OU EXCLUSIF (XOR) entre:\n"
        elif self.opcode in ("SUB", "CMP"):
            modifiedFlags.update(('C', 'V'))
            description += "<li>Effectue une soustraction (A-B) entre:\n"
            if self.opcode == "SUB" and self.rd == 15:
                # We change PC, we show it in the editor
                self._nextline = simulatorContext.regs[self.rn].get() - op2
        elif self.opcode == "RSB":
            modifiedFlags.update(('C', 'V'))
            description += "<li>Effectue une soustraction inverse (B-A) entre:\n"
        elif self.opcode in ("ADD", "CMN"):
            modifiedFlags.update(('C', 'V'))
            description += "<li>Effectue une addition (A+B) entre:\n"
            if self.opcode == "ADD" and self.rd == 15:
                # We change PC, we show it in the editor
                self._nextline = simulatorContext.regs[self.rn].get() + op2
        elif self.opcode == "ADC":
            modifiedFlags.update(('C', 'V'))
            description += "<li>Effectue une addition avec retenue (A+B+carry) entre:\n"
        elif self.opcode == "SBC":
            modifiedFlags.update(('C', 'V'))
            description += "<li>Effectue une soustraction avec emprunt (A-B+carry) entre:\n"
        elif self.opcode == "RSC":
            modifiedFlags.update(('C', 'V'))
            description += "<li>Effectue une soustraction inverse avec emprunt (B-A+carry) entre:\n"
        elif self.opcode == "ORR":
            description += "<li>Effectue une opération OU entre:\n"
        elif self.opcode == "MOV":
            description += "<li>Lit la valeur de :\n"
            if self.rd == 15:
                # We change PC, we show it in the editor
                self._nextline = op2
        elif self.opcode == "BIC":
            description += "<li>Effectue une opération ET NON entre:\n"
        elif self.opcode == "MVN":
            description += "<li>Effectue une opération NOT sur :\n"
            if self.rd == 15:
                # We change PC, we show it in the editor
                self._nextline = ~op2
        else:
            assert False, "Bad data opcode : " + self.opcode

        if self.opcode in ("MOV", "MVN"):
            description += "<ol type=\"A\"><li>{}</li></ol>\n".format(op2desc)
            disassembly += " R{}, ".format(self.rd)
        elif self.opcode in ("TST", "TEQ", "CMP", "CMN"):
            description += "<ol type=\"A\"><li>Le registre {}</li><li>{}</li></ol>\n".format(utils.regSuffixWithBank(self.rn, bank), op2desc)
            disassembly += " R{}, ".format(self.rn)
        else:
            description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(_regSuffixWithBank(self.rn))
            description += "<li>{}</li></ol>\n".format(op2desc)
            disassembly += " R{}, R{}, ".format(self.rd, self.rn)
        disassembly += op2dis

        description += "</li>\n"

        if self.modifyFlags:
            if self.rd == 15:
                description += "<li>Copie le SPSR courant dans CPSR</li>\n"
            else:
                self._modflags = tuple(modifiedFlags)
                description += "<li>Met à jour les drapeaux de l'ALU en fonction du résultat de l'opération</li>\n"
        if self.opcode not in ("TST", "TEQ", "CMP", "CMN"):
            description += "<li>Écrit le résultat dans {}</li>".format(utils.regSuffixWithBank(self.rd, bank))
            highlightwrite.extend(utils.registerWithCurrentBank(self.rd, bank))

        description += "</ol>"

        return disassembly, description
        #dis = '<div id="disassembly_instruction">{}</div>\n<div id="disassembly_description">{}</div>\n'.format(disassembly, description)
    

    def execute(self, simulatorContext):
        workingFlags['C'] = 0
        workingFlags['V'] = 0
        # Get first operand value
        op1 = simulatorContext.regs[self.rn].get()
        # Get second operand value
        if self.imm:
            op2 = self.shiftedVal
        else:
            op2 = simulatorContext.regs[self.op2reg].get()
            if self.op2reg == 15 and not self.shift.immediate and simulatorContext.PCbehavior == "real":
                op2 += 4    # Special case for PC where we use PC+12 instead of PC+8 (see 4.5.5 of ARM Instr. set)
            carry, op2 = utils.applyShift(op2, self.shift, simulatorContext.flags['C'])
            workingFlags['C'] = bool(carry)

        if self.opcode in ("AND", "TST"):
            # These instructions do not affect the V flag (ARM Instr. set, 4.5.1)
            # However, C flag "is set to the carry out from the barrel shifter [if the shift is not LSL #0]" (4.5.1)
            # this was already done when we called _shiftVal
            res = op1 & op2
        elif self.opcode in ("EOR", "TEQ"):
            # These instructions do not affect the C and V flags (ARM Instr. set, 4.5.1)
            res = op1 ^ op2
        elif self.opcode in ("SUB", "CMP"):
            # For a subtraction, including the comparison instruction CMP, C is set to 0
            # if the subtraction produced a borrow (that is, an unsigned underflow), and to 1 otherwise.
            # http://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.dui0801a/CIADCDHH.html
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(op1, ~op2, 1)
        elif self.opcode == "RSB":
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(~op1, op2, 1)
        elif self.opcode in ("ADD", "CMN"):
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(op1, op2, 0)
        elif self.opcode== "ADC":
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(op1, op2, int(simulatorContext.flags['C']))
        elif self.opcode == "SBC":
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(op1, ~op2, int(simulatorContext.flags['C']))
        elif self.opcode == "RSC":
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(~op1, op2, int(simulatorContext.flags['C']))
        elif self.opcode == "ORR":
            res = op1 | op2
        elif self.opcode == "MOV":
            res = op2
        elif self.opcode == "BIC":
            res = op1 & ~op2     # Bit clear?
        elif self.opcode == "MVN":
            res = ~op2
        else:
            raise ExecutionException("Mnémonique invalide : {}".format(self.opcode))

        res &= 0xFFFFFFFF           # Get the result back to 32 bits, if applicable (else it's just a no-op)

        workingFlags['Z'] = res == 0
        workingFlags['N'] = res & 0x80000000            # "N flag will be set to the value of bit 31 of the result" (4.5.1)

        if self.modifyFlags:
            if self.rd == 15:
                # Combining writing to PC and the S flag is a special case (see ARM Instr. set, 4.5.5)
                # "When Rd is R15 and the S flag is set the result of the operation is placed in R15 and
                # the SPSR corresponding to the current mode is moved to the CPSR. This allows state
                # changes which atomically restore both PC and CPSR. This form of instruction should
                # not be used in User mode."
                if simulatorContext.getCPSR().getMode() == "User":
                    raise ExecutionException("L'utilisation de PC comme registre de destination en combinaison avec la mise a jour des drapeaux est interdite en mode User!")
                simulatorContext.regs.getCPSR().set(simulatorContext.regs.getSPSR().get())          # Put back the saved SPSR in CPSR
                simulatorContext.regs.setCurrentBankFromMode(simulatorContext.regs.getCPSR().get() & 0x1F)
            else:
                simulatorContext.flags.update(workingFlags)

        if misc['opcode'] not in ("TST", "TEQ", "CMP", "CMN"):
            # We actually write the result
            simulatorContext.regs[self.rd].set(res)

    @property
    def affectedRegs(self):
        return () if 7 < self.opcodeNum < 12 else (self.rd,)

    @property
    def affectedFlags(self):
        return self._modflags

    @property
    def nextLineToExecute(self):
        return self._nextline

    @property
    def pcHasChanged(self):
        return self.rd == 15