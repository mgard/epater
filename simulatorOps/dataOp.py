import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import utils
from abstractOp import AbstractOp

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
            self.val = instrInt & 0xFF
            # see 4.5.3 of ARM doc to understand the * 2
            self.shift = utils.shiftInfo(type="ROR", 
                                            immediate=True, 
                                            value=((instrInt >> 8) & 0xF) * 2)
        else:
            self.val = instrInt & 0xF
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
            op2 = self.val
            if self.shift.value != 0:
                carry, op2 = utils.applyShift(op2, self.shift, simulatorContext.flags['C'])
            op2desc = "La constante {}".format(op2)
            op2dis = "#{}".format(hex(op2))
        else:
            highlightread.extend(utils.registerWithCurrentBank(self.val, bank))
            
            if self.shift.type != "LSL" or self.shift.value > 0 or not self.shift.immediate:
                modifiedFlags.add('C')

            shiftDesc = utils.shiftToDescription(self.shift, bank)
            shiftinstr = utils.shiftToInstruction(self.shift)
            op2desc = "Le registre {} {}".format(utils.regSuffixWithBank(self.shift.value, bank), shiftDesc)
            op2dis = "R{}{}".format(self.val, shiftinstr)
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
            description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(_regSuffixWithBank(misc['rn']))
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

        dis = '<div id="disassembly_instruction">{}</div>\n<div id="disassembly_description">{}</div>\n'.format(disassembly, description)
    
    def execute(self):
        pass

    @property
    def affectedRegs(self):
        return () if 7 < self.opcodeNum < 12 else (self.rd,)

    @property
    def affectedFlags(self):
        return self._modflags

    @property
    def nextLineToExecute(self):
        return self._nextline 