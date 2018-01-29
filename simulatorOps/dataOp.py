import operator
import struct
from enum import Enum
from collections import defaultdict, namedtuple, deque 

import simulatorOps.utils as utils
from simulatorOps.abstractOp import AbstractOp, ExecutionException

class DataOp(AbstractOp):
    saveStateKeys = frozenset(("condition", 
                                "opcodeNum", "opcode", 
                                "imm", "modifyFlags", 
                                "rd", "rn", 
                                "shiftedVal", "shift", "carryOutImmShift", "op2reg"))

    def __init__(self):
        super().__init__()
        self._type = utils.InstrType.dataop

    def decode(self):
        instrInt = self.instrInt
        if not utils.checkMask(instrInt, (), (27, 26)):
            raise ExecutionException("masque de décodage invalide pour une instruction de type DATA", 
                                        internalError=True)

        # Retrieve the condition field
        self._decodeCondition()

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
            self.carryOutImmShift = 0
            if self.shift.value != 0:
                # If it is a constant, we shift as we decode
                self.carryOutImmShift, self.shiftedVal = utils.applyShift(self.shiftedVal, 
                                                                            self.shift, 
                                                                            False)
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
        self.resetAccessStates()
        bank = simulatorContext.regs.mode
        simulatorContext.regs.deactivateBreakpoints()
        modifiedFlags = {'Z', 'N'}

        disassembly = self.opcode
        description = "<ol>\n"
        disCond, descCond = self._explainCondition()
        disassembly += disCond
        description += descCond

        if self.modifyFlags and self.opcode not in ("TST", "TEQ", "CMP", "CMN"):
            disassembly += "S"

        op1 = simulatorContext.regs[self.rn]
        if self.opcode not in ("MOV", "MVN"):
            self._readregs |= utils.registerWithCurrentBank(self.rn, bank)

        op2desc = ""
        op2dis = ""
        # Get second operand value
        if self.imm:
            op2 = self.shiftedVal
            op2desc = "La constante {}".format(op2)
            op2dis = "#{}".format(hex(op2))
        else:
            self._readregs |= utils.registerWithCurrentBank(self.op2reg, bank)
            
            if self.shift.type != "LSL" or self.shift.value > 0 or not self.shift.immediate:
                modifiedFlags.add('C')

            shiftDesc = utils.shiftToDescription(self.shift, bank)
            shiftinstr = utils.shiftToInstruction(self.shift)
            op2desc = "Le registre {} {}".format(utils.regSuffixWithBank(self.op2reg, bank), shiftDesc)
            op2dis = "R{}{}".format(self.op2reg, shiftinstr)
            if not self.shift.immediate:
                self._readregs |= utils.registerWithCurrentBank(self.shift.value, bank)

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
            if self.opcode == "SUB" and self.rd == simulatorContext.PC:
                # We change PC, we show it in the editor
                self._nextInstrAddr = simulatorContext.regs[self.rn] - op2
        elif self.opcode == "RSB":
            modifiedFlags.update(('C', 'V'))
            description += "<li>Effectue une soustraction inverse (B-A) entre:\n"
        elif self.opcode in ("ADD", "CMN"):
            modifiedFlags.update(('C', 'V'))
            description += "<li>Effectue une addition (A+B) entre:\n"
            if self.opcode == "ADD" and self.rd == simulatorContext.PC:
                # We change PC, we show it in the editor
                self._nextInstrAddr = simulatorContext.regs[self.rn] + op2
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
            if self.rd == simulatorContext.PC:
                # We change PC, we show it in the editor
                self._nextInstrAddr = op2
        elif self.opcode == "BIC":
            description += "<li>Effectue une opération ET NON entre:\n"
        elif self.opcode == "MVN":
            description += "<li>Effectue une opération NOT sur :\n"
            if self.rd == simulatorContext.PC:
                # We change PC, we show it in the editor
                self._nextInstrAddr = ~op2
        else:
            raise ExecutionException("Mnémonique invalide : {}".format(self.opcode))

        if self.opcode in ("MOV", "MVN"):
            description += "<ol type=\"A\"><li>{}</li></ol>\n".format(op2desc)
            disassembly += " R{}, ".format(self.rd)
        elif self.opcode in ("TST", "TEQ", "CMP", "CMN"):
            description += "<ol type=\"A\"><li>Le registre {}</li><li>{}</li></ol>\n".format(utils.regSuffixWithBank(self.rn, bank), op2desc)
            disassembly += " R{}, ".format(self.rn)
        else:
            description += "<ol type=\"A\"><li>Le registre {}</li>\n".format(utils.regSuffixWithBank(self.rn, bank))
            description += "<li>{}</li></ol>\n".format(op2desc)
            disassembly += " R{}, R{}, ".format(self.rd, self.rn)
        disassembly += op2dis

        description += "</li>\n"

        if self.modifyFlags:
            if self.rd == simulatorContext.PC:
                description += "<li>Copie le SPSR courant dans CPSR</li>\n"
            else:
                self._writeflags = modifiedFlags
                description += "<li>Met à jour les drapeaux de l'ALU en fonction du résultat de l'opération</li>\n"
        if self.opcode not in ("TST", "TEQ", "CMP", "CMN"):
            description += "<li>Écrit le résultat dans {}</li>".format(utils.regSuffixWithBank(self.rd, bank))
            self._writeregs |= utils.registerWithCurrentBank(self.rd, bank)

        description += "</ol>"

        simulatorContext.regs.reactivateBreakpoints()
        return disassembly, description
    
    def execute(self, simulatorContext):
        self.pcmodified = False
        if not self._checkCondition(simulatorContext.regs):
            # Nothing to do, instruction not executed
            self.countExecConditionFalse += 1
            return
        self.countExec += 1
        
        workingFlags = {}
        workingFlags['C'] = 0
        # "On logical operations, if the S bit is set (and Rd is not R15)
        # the V flag in the CPSR will be unaffected"
        # (ARM Reference 4.5.1)
        workingFlags['V'] = simulatorContext.regs.V
        # Get first operand value
        op1 = simulatorContext.regs[self.rn]
        # Get second operand value
        if self.imm:
            op2 = self.shiftedVal
            if self.shift.value != 0:
                # We change the carry flag only if we did a shift
                workingFlags['C'] = self.carryOutImmShift
            else:
                workingFlags['C'] = simulatorContext.regs.C
        else:
            op2 = simulatorContext.regs[self.op2reg]
            if self.op2reg == simulatorContext.PC and not self.shift.immediate and simulatorContext.PCSpecialBehavior:
                op2 += 4    # Special case for PC where we use PC+12 instead of PC+8 (see 4.5.5 of ARM Instr. set)
            carry, op2 = utils.applyShift(op2, self.shift, simulatorContext.regs.C)
            workingFlags['C'] = bool(carry)

        if self.opcode == "MOV":
            res = op2
        elif self.opcode in ("ADD", "CMN"):
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(op1, op2, 0)
        elif self.opcode in ("SUB", "CMP"):
            # For a subtraction, including the comparison instruction CMP, C is set to 0
            # if the subtraction produced a borrow (that is, an unsigned underflow), and to 1 otherwise.
            # http://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.dui0801a/CIADCDHH.html
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(op1, ~op2, 1)
        elif self.opcode == "MVN":
            res = ~op2
        elif self.opcode in ("AND", "TST"):
            # These instructions do not affect the V flag (ARM Instr. set, 4.5.1)
            # However, C flag "is set to the carry out from the barrel shifter [if the shift is not LSL #0]" (4.5.1)
            # this was already done when we called _shiftVal
            res = op1 & op2
        elif self.opcode == "ORR":
            res = op1 | op2
        elif self.opcode == "BIC":
            res = op1 & ~op2     # Bit clear?
        elif self.opcode in ("EOR", "TEQ"):
            # These instructions do not affect the C and V flags (ARM Instr. set, 4.5.1)
            res = op1 ^ op2
        elif self.opcode == "RSB":
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(~op1, op2, 1)
        elif self.opcode== "ADC":
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(op1, op2, int(simulatorContext.regs.C))
        elif self.opcode == "SBC":
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(op1, ~op2, int(simulatorContext.regs.C))
        elif self.opcode == "RSC":
            res, workingFlags['C'], workingFlags['V'] = utils.addWithCarry(~op1, op2, int(simulatorContext.regs.C))
        else:
            raise ExecutionException("Mnémonique invalide : {}".format(self.opcode))

        # Get the result back to 32 bits, if applicable (else it's just a no-op)
        res &= 0xFFFFFFFF           

        workingFlags['Z'] = res == 0
         # "N flag will be set to the value of bit 31 of the result" (4.5.1)
        workingFlags['N'] = res & 0x80000000

        if self.modifyFlags:
            if self.rd == simulatorContext.PC:
                # Combining writing to PC and the S flag is a special case (see ARM Instr. set, 4.5.5)
                # "When Rd is R15 and the S flag is set the result of the operation is placed in R15 and
                # the SPSR corresponding to the current mode is moved to the CPSR. This allows state
                # changes which atomically restore both PC and CPSR. This form of instruction should
                # not be used in User mode."
                if simulatorContext.regs.mode == "User":
                    raise ExecutionException("L'utilisation de PC comme registre de destination en combinaison avec la mise a jour des drapeaux est interdite en mode User!")
                simulatorContext.regs.CPSR = simulatorContext.regs.SPSR        # Put back the saved SPSR in CPSR
            else:
                simulatorContext.regs.setAllFlags(workingFlags)

        if self.opcode not in ("TST", "TEQ", "CMP", "CMN"):
            # We actually write the result
            simulatorContext.regs[self.rd] = res
            if self.rd == simulatorContext.PC:
                self.pcmodified = True

