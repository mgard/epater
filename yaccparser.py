import struct
import ply.yacc as yacc

from tokenizer import tokens, ParserError
from settings import getSetting

import instruction

class YaccError(ParserError):
    """
    The exception class used when the lexer encounter an invalid syntax.
    """
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

currentMnemonic = ""

def p_line(p):
    """line : ENDLINESPACES
            | COMMENT ENDLINESPACES
            | linelabel ENDLINESPACES
            | linelabelinstr ENDLINESPACES
            | lineinstruction ENDLINESPACES
            | sectiondeclaration ENDLINESPACES
            | linedeclaration ENDLINESPACES
            | lineassertion ENDLINESPACES"""
    p[0] = p[1] if isinstance(p[1], dict) else {}


def p_linelabel(p):
    """linelabel : LABEL
                 | LABEL COMMENT"""
    p[0] = {'LABEL': p[1]}

def p_linelabel_error(p):
    """linelabel : LABEL error COMMA"""
    raise YaccError("Instruction invalide : \"{}\". Veuillez vous référer au manuel du simulateur pour la liste des instructions acceptées. ".format(p[1]))


def p_sectiondeclaration(p):
    """sectiondeclaration : SECTION SECTIONNAME
                          | SECTION SECTIONNAME COMMENT"""
    p[0] = {'SECTION': p[2]}

def p_lineassertion(p):
    """lineassertion : ASSERTION ASSERTIONDATA
                     | ASSERTION ASSERTIONDATA COMMENT"""
    p[0] = {'ASSERTION': p[2]}

def p_linedeclaration(p):
    """linedeclaration : LABEL SPACEORTAB declarationconst
                       | LABEL SPACEORTAB declarationconst COMMENT
                       | LABEL SPACEORTAB declarationsize
                       | LABEL SPACEORTAB declarationsize COMMENT"""
    p[0] = {'LABEL': p[1], 'BYTECODE': p[3]}

def p_lineinstruction(p):
    """lineinstruction : instruction
                       | instruction COMMENT"""
    p[0] = {'BYTECODE': p[1]}

def p_linelabelinstr(p):
    """linelabelinstr : LABEL SPACEORTAB instruction
                      | LABEL SPACEORTAB instruction COMMENT"""
    p[0] = {'LABEL': p[1], 'BYTECODE': p[3]}

def p_instruction(p):
    """instruction : datainstruction
                   | meminstruction
                   | branchinstruction
                   | multiplememinstruction
                   | shiftinstruction
                   | psrinstruction
                   | svcinstruction
                   | multiplyinstruction"""
    # We just shift the instruction bytecode and dependencies to the next level
    p[0] = p[1]

def p_datainstruction(p):
    """datainstruction : datainst2op
                       | datainst3op
                       | datainsttest"""
    # A data op instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", p[1]), None)

def p_datainst2op(p):
    """datainst2op : OPDATA2OP logmnemonic SPACEORTAB REG COMMA op2
                   | OPDATA2OP logmnemonic CONDITION SPACEORTAB REG COMMA op2
                   | OPDATA2OP logmnemonic MODIFYFLAGS SPACEORTAB REG COMMA op2
                   | OPDATA2OP logmnemonic MODIFYFLAGS CONDITION SPACEORTAB REG COMMA op2"""
    # Create a list from the Yacc generator (so we can use negative indices)
    plist = list(p)
    # We build the instruction bytecode
    # Add the mnemonic
    # We DON'T use plist[1] because the op2 rule might have changed it (to fit a constant)!
    b = instruction.dataOpcodeMapping[currentMnemonic] << 21
    # Add the destination register
    b |= plist[-3] << 12
    # Add the second operand
    b |= plist[-1]

    conditionSet = False
    if len(plist) == 8:
        if plist[3] == 'S':
            # Set flags
            b |= 1 << 20
        else:
            # Set condition
            b |= instruction.conditionMapping[plist[3]] << 28
            conditionSet = True
    if len(plist) == 9:
        # Set flags
        b |= 1 << 20
        # Set condition
        b |= instruction.conditionMapping[plist[4]] << 28
        conditionSet = True

    if not conditionSet:
        # Set AL condition
        b |= instruction.conditionMapping['AL'] << 28

    # We return the bytecode
    p[0] = b

def p_datainst2op_error(p):
    """datainst2op : OPDATA2OP logmnemonic SPACEORTAB REG error op2"""
    raise YaccError("Les registres et/ou constantes utilisés dans une opération doivent être séparés par une virgule")

def p_datainst3op(p):
    """datainst3op : OPDATA3OP logmnemonic SPACEORTAB REG COMMA REG COMMA op2
                   | OPDATA3OP logmnemonic CONDITION SPACEORTAB REG COMMA REG COMMA op2
                   | OPDATA3OP logmnemonic MODIFYFLAGS SPACEORTAB REG COMMA REG COMMA op2
                   | OPDATA3OP logmnemonic MODIFYFLAGS CONDITION SPACEORTAB REG COMMA REG COMMA op2"""
    # Create a list from the Yacc generator (so we can use negative indices)
    plist = list(p)
    # We build the instruction bytecode
    # Add the mnemonic
    # We DON'T use plist[1] because the op2 rule might have changed it (to fit a constant)!
    b = instruction.dataOpcodeMapping[currentMnemonic] << 21
    # Add the destination register
    b |= plist[-5] << 12
    # Add the first register operand
    b |= plist[-3] << 16
    # Add the second operand
    b |= plist[-1]

    conditionSet = False
    if len(plist) == 10:
        if plist[3] == 'S':
            # Set flags
            b |= 1 << 20
        else:
            # Set condition
            b |= instruction.conditionMapping[plist[3]] << 28
            conditionSet = True
    if len(plist) == 11:
        # Set flags
        b |= 1 << 20
        # Set condition
        b |= instruction.conditionMapping[plist[4]] << 28
        conditionSet = True

    if not conditionSet:
        # Set AL condition
        b |= instruction.conditionMapping['AL'] << 28
    # We return the bytecode
    p[0] = b

def p_datainst3op_error(p):
    """datainst3op : OPDATA3OP logmnemonic SPACEORTAB REG COMMA REG error ENDLINESPACES
                   | OPDATA3OP logmnemonic SPACEORTAB REG error COMMA"""
    print("!!!!!", len(p))
    if len(p) == 9:
        raise YaccError("L'instruction {} requiert 3 arguments".format(p[1]))
    else:
        raise YaccError("Le registre R{}{} n'existe pas".format(p[4], p[5]))

def p_datainsttest(p):
    """datainsttest : OPDATATEST logmnemonic SPACEORTAB REG COMMA op2
                    | OPDATATEST logmnemonic CONDITION SPACEORTAB REG COMMA op2"""
    # Create a list from the Yacc generator (so we can use negative indices)
    plist = list(p)
    # We build the instruction bytecode
    # Add the mnemonic
    # We DON'T use plist[1] because the op2 rule might have changed it (to fit a constant)!
    b = instruction.dataOpcodeMapping[currentMnemonic] << 21
    # Add the first register operand
    b |= plist[-3] << 16
    # Add the second operand
    b |= plist[-1]

    # We always add the S bit
    b |= 1 << 20

    if len(plist) == 8:
        # Set condition
        b |= instruction.conditionMapping[plist[3]] << 28
    else:
        # Set AL condition
        b |= instruction.conditionMapping['AL'] << 28

    # We return the bytecode
    p[0] = b

def p_logmnemonic(p):
    """logmnemonic :"""
    # Dummy rule to log the mnemonic as soon as we see it (will be used by the next rule)
    global currentMnemonic
    currentMnemonic = p[-1]

def p_op2(p):
    """op2 : REG
           | SHARP CONST
           | REG COMMA shift"""
    global currentMnemonic
    assert currentMnemonic != ""
    plist = list(p)
    if len(plist) == 2:
        # Register only
        p[0] = plist[1]
    elif len(plist) == 3:
        # Constant
        p[0] = 1 << 25
        typeInverse = None
        if currentMnemonic in ('MOV', 'MVN', 'AND', 'BIC'):
            typeInverse = 'logical'
        elif currentMnemonic in ('ADD', 'SUB', 'CMP', 'CMN'):
            typeInverse = 'arithmetic'
        ret = instruction.immediateToBytecode(plist[2], typeInverse)
        if ret is None:
            # Unable to encode constant
            raise YaccError("Impossible d'encoder la constante suivante ou son inverse dans une instruction {} : {}".format(currentMnemonic, plist[2]))
        immval, immrot, inverse = ret
        if inverse and currentMnemonic not in instruction.dataOpcodeInvert.keys():
            # We could fit the constant by inverting it, but we do not have invert operation for this mnemonic
            raise YaccError("Impossible d'encoder la constante suivante dans une instruction {} : {}".format(currentMnemonic, plist[2]))
        elif inverse:
            # We switch the mnemonic
            currentMnemonic = instruction.dataOpcodeInvert[currentMnemonic]
        # We encode the shift
        p[0] |= immval
        p[0] |= immrot << 8
    elif len(plist) == 4:
        # Shifted register
        p[0] = plist[1]
        p[0] |= plist[3]

def p_op2_error(p):
    """op2 : error"""
    print("BOUM")

def p_shift(p):
    """shift : INNERSHIFT
             | INNERSHIFT SPACEORTAB REG
             | INNERSHIFT SPACEORTAB SHARP CONST"""
    plist = list(p)
    # Shift type
    if len(plist) == 4 and p[4] == 0 and p[1] in ('LSR', 'ASR', 'ROR'):
        # "Logical shift right zero is redundant as it is the same as logical shift left zero, so the assembler
        # will convert LSR #0 (and ASR #0 and ROR #0) into LSL #0, and allow LSR #32 to be specified."
        p[0] = instruction.shiftMapping['LSL'] << 5
    else:
        p[0] = instruction.shiftMapping[p[1]] << 5
    if len(plist) == 2:
        # Special case, must be RRX
        assert p[1] == "RRX"
    elif len(plist) == 4:
        # Shift by register
        p[0] |= 1 << 4
        p[0] |= p[3] << 8
    elif not (p[1] in ('LSR', 'ASR') and p[4] == 32):
        # Shift by a constant if we are not in special modes
        if p[4] < 0:
            raise YaccError("Impossible d'encoder un décalage négatif ({}) dans une instruction (utilisez un autre opérateur de décalage pour arriver au même effet)".format(p[4]))
        if p[4] > 31:
            raise YaccError("Impossible d'encoder le décalage {} dans une instruction (ce dernier doit être inférieur à 32)".format(p[4]))
        p[0] |= p[4] << 7




def p_shiftinstruction(p):
    """shiftinstruction : shiftinstrconst
                        | shiftinstrreg
                        | shiftinstrrrx"""
    # We always use a MOV with these pseudo-operations
    p[0] = instruction.dataOpcodeMapping["MOV"] << 21
    # Shift type
    p[0] |= p[1]

    # A shift instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", p[0]), None)

def p_shiftinstrrrx(p):
    """shiftinstrrrx : OPSHIFT logmnemonic SPACEORTAB REG COMMA REG
                     | OPSHIFT logmnemonic MODIFYFLAGS SPACEORTAB REG COMMA REG
                     | OPSHIFT logmnemonic CONDITION SPACEORTAB REG COMMA REG
                     | OPSHIFT logmnemonic MODIFYFLAGS CONDITION SPACEORTAB REG COMMA REG"""
    plist = list(p)
    assert p[1] == "RRX"
    p[0] = instruction.shiftMapping[p[1]] << 5

    # Source register
    p[0] |= plist[-1]
    # Destination register
    p[0] |= plist[-3] << 12

    conditionSet = False
    if len(plist) == 8:
        if plist[3] == 'S':
            # Set flags
            p[0] |= 1 << 20
        else:
            # Set condition
            p[0] |= instruction.conditionMapping[plist[3]] << 28
            conditionSet = True
    if len(plist) == 9:
        # Set flags
        p[0] |= 1 << 20
        # Set condition
        p[0] |= instruction.conditionMapping[plist[4]] << 28
        conditionSet = True

    if not conditionSet:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28

def p_shiftinstrconst(p):
    """shiftinstrconst : OPSHIFT logmnemonic SPACEORTAB REG COMMA REG COMMA SHARP CONST
                       | OPSHIFT logmnemonic MODIFYFLAGS SPACEORTAB REG COMMA REG COMMA SHARP CONST
                       | OPSHIFT logmnemonic CONDITION SPACEORTAB REG COMMA REG COMMA SHARP CONST
                       | OPSHIFT logmnemonic MODIFYFLAGS CONDITION SPACEORTAB REG COMMA REG COMMA SHARP CONST"""
    global currentMnemonic
    plist = list(p)
    # Shift mode
    p[0] = instruction.shiftMapping[p[1]] << 5
    # We shift by a constant
    # Destination register
    p[0] |= plist[-6] << 12
    # Source register
    p[0] |= plist[-4]
    # Retrieve and check the constant value
    const = plist[-1]
    assert 0 <= const <= 32
    if not (currentMnemonic in ('LSR', 'ASR') and const == 32):     # Special cases
        p[0] |= const << 7

    conditionSet = False
    if len(plist) == 11:
        if plist[3] == 'S':
            # Set flags
            p[0] |= 1 << 20
        else:
            # Set condition
            p[0] |= instruction.conditionMapping[plist[3]] << 28
            conditionSet = True
    if len(plist) == 12:
        # Set flags
        p[0] |= 1 << 20
        # Set condition
        p[0] |= instruction.conditionMapping[plist[4]] << 28
        conditionSet = True

    if not conditionSet:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28


def p_shiftinstrreg(p):
    """shiftinstrreg : OPSHIFT logmnemonic SPACEORTAB REG COMMA REG COMMA REG
                     | OPSHIFT logmnemonic MODIFYFLAGS SPACEORTAB REG COMMA REG COMMA REG
                     | OPSHIFT logmnemonic CONDITION SPACEORTAB REG COMMA REG COMMA REG
                     | OPSHIFT logmnemonic MODIFYFLAGS CONDITION SPACEORTAB REG COMMA REG COMMA REG"""
    plist = list(p)
    # Shift mode
    p[0] = instruction.shiftMapping[p[1]] << 5
    # We shift by a register
    p[0] |= 1 << 4
    # Destination register
    p[0] |= plist[-5] << 12
    # Source register
    p[0] |= plist[-3]
    # Shift register
    p[0] |= plist[-1] << 8

    conditionSet = False
    if len(plist) == 10:
        if plist[3] == 'S':
            # Set flags
            p[0] |= 1 << 20
        else:
            # Set condition
            p[0] |= instruction.conditionMapping[plist[3]] << 28
            conditionSet = True
    if len(plist) == 11:
        # Set flags
        p[0] |= 1 << 20
        # Set condition
        p[0] |= instruction.conditionMapping[plist[4]] << 28
        conditionSet = True

    if not conditionSet:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28


def p_meminstruction(p):
    """meminstruction : OPMEM logmnemonic SPACEORTAB REG COMMA memaccess
                      | OPMEM logmnemonic CONDITION SPACEORTAB REG COMMA memaccess
                      | OPMEM logmnemonic BYTEONLY SPACEORTAB REG COMMA memaccess
                      | OPMEM logmnemonic BYTEONLY CONDITION SPACEORTAB REG COMMA memaccess"""
    global currentMnemonic
    # Create a list from the Yacc generator (so we can use negative indices)
    plist = list(p)
    # We build the instruction bytecode
    # Add the mnemonic and the bit signaling this as a memory operation
    p[0] = 1 << 26
    p[0] |= (1 << 20 if currentMnemonic == "LDR" else 0)

    # Add the source/destination register
    p[0] |= plist[-3] << 12

    # Add the memory access info
    memaccessinfo = plist[-1]
    p[0] |= memaccessinfo[0]

    conditionSet = False
    if len(plist) == 8:
        if plist[3] == 'B':
            # Set bytes mode
            p[0] |= 1 << 22
        else:
            # Set condition
            p[0] |= instruction.conditionMapping[plist[3]] << 28
            conditionSet = True
    if len(plist) == 9:
        # Set bytes mode
        p[0] |= 1 << 22
        # Set condition
        p[0] |= instruction.conditionMapping[plist[4]] << 28
        conditionSet = True

    if not conditionSet:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28

    # We return the bytecode, with the eventual dependencies
    p[0] = (struct.pack("<I", p[0]), memaccessinfo[1])

def p_memaccess(p):
    """memaccess : memaccesspre
                 | memaccesspost
                 | memaccesslabel
                 | memaccesslabeladdr"""
    # We divide pre and post increment to simplify their respective rules
    p[0] = p[1]

def p_memaccesspre(p):
    """memaccesspre : OPENBRACKET REG CLOSEBRACKET
                    | OPENBRACKET REG COMMA REG CLOSEBRACKET
                    | OPENBRACKET REG COMMA REG CLOSEBRACKET EXCLAMATION
                    | OPENBRACKET REG COMMA SHARP CONST CLOSEBRACKET
                    | OPENBRACKET REG COMMA SHARP CONST CLOSEBRACKET EXCLAMATION
                    | OPENBRACKET REG COMMA REG COMMA shiftnoreg CLOSEBRACKET
                    | OPENBRACKET REG COMMA REG COMMA shiftnoreg CLOSEBRACKET EXCLAMATION"""
    plist = list(p)
    p[0] = plist[2] << 16
    p[0] |= 1 << 24         # Pre indexing bit

    if plist[-1] == "!":    # Writeback
        p[0] |= 1 << 21

    if len(plist) > 4:
        if plist[4] == "#":     # Constant offset
            if plist[5] >= 0:
                p[0] |= 1 << 23
            offset = abs(plist[5])
            if offset > 2**12-1:
                # Cannot encode the offset
                raise YaccError("Le décalage de {} demandé dans l'instruction est trop élevé pour pouvoir être encodé (il doit être inférieur à 4096)".format(offset))
            p[0] |= offset & 0xFFF
        else:                   # Register offset
            p[0] |= 1 << 25
            p[0] |= 1 << 23         # We always add the offset if it is a register
            p[0] |= plist[4]
            if ',' in plist[5]:     # We have a shift
                p[0] |= plist[6]
    else:
        p[0] |= 1 << 23     # Default mode is UP (even if there is no offset)

    p[0] = (p[0], None)     # No external dependencies (this instruction is self contained, no reference to labels)

def p_shiftnoreg(p):
    """shiftnoreg : INNERSHIFT
                  | INNERSHIFT SPACEORTAB SHARP CONST"""
    # Special shift for the LDR/STR operations : only shift by a constant is allowed
    plist = list(p)
    p[0] = instruction.shiftMapping[p[1]] << 5
    if len(plist) == 2:
        # Special case, must be RRX
        assert p[1] == "RRX"
    elif not (p[1] in ('LSR', 'ASR') and p[4] == 32):
        # Shift by a constant if we are not in special modes
        p[0] |= p[4] << 7

def p_memacesspost(p):
    """memaccesspost : OPENBRACKET REG CLOSEBRACKET COMMA REG
                     | OPENBRACKET REG CLOSEBRACKET COMMA REG COMMA shiftnoreg
                     | OPENBRACKET REG CLOSEBRACKET COMMA SHARP CONST"""
    plist = list(p)
    p[0] = plist[2] << 16

    if plist[5] == "#":     # Constant offset
        if plist[6] > 0:
            p[0] |= 1 << 23
        offset = abs(plist[6])
        if offset > 2**12-1:
            # Cannot encode the offset
            raise YaccError("Le décalage de {} demandé dans l'instruction est trop élevé pour pouvoir être encodé (il doit être inférieur à 4096)".format(offset))
        p[0] |= offset & 0xFFF
    else:                   # Register offset
        p[0] |= 1 << 25
        p[0] |= 1 << 23  # We always add the offset if it is a register
        p[0] |= plist[5]
        if len(plist) > 7:  # We have a shift
            p[0] |= plist[7]

    p[0] = (p[0], None)     # No external dependencies (this instruction is self contained, no reference to labels)

def p_memaccesslabel(p):
    """memaccesslabel : LABEL"""
    # We will use PC as label
    b = 15 << 16
    # Pre-indexing
    b |= 1 << 24
    p[0] = (b, ("addr", p[1]))     # This instruction cannot be assembled yet: we need to know the label's address

def p_memaccesslabeladdr(p):
    """memaccesslabeladdr : EQUALS LABEL"""
    # We will use PC as label
    b = 15 << 16
    # Pre-indexing
    b |= 1 << 24
    p[0] = (b, ("addrptr", p[2]))     # This instruction cannot be assembled yet: we need to know the label's address


def p_branchinstruction(p):
    """branchinstruction : OPBRANCH logmnemonic SPACEORTAB LABEL
                         | OPBRANCH logmnemonic SPACEORTAB REG
                         | OPBRANCH logmnemonic CONDITION SPACEORTAB LABEL
                         | OPBRANCH logmnemonic CONDITION SPACEORTAB REG"""
    global currentMnemonic
    # Create a list from the Yacc generator (so we can use negative indices)
    plist = list(p)
    mode = "reg" if isinstance(plist[-1], int) else "label"
    # We build the instruction bytecode
    if currentMnemonic == 'BX':
        assert mode == "reg"
        p[0] = 0b000100101111111111110001 << 4
        p[0] |= plist[-1]
    else:
        assert mode == "label"
        p[0] = 5 << 25
        if currentMnemonic == 'BL':
            p[0] |= 1 << 24

    if len(plist) == 6:
        # We have a condition
        p[0] |= instruction.conditionMapping[plist[3]] << 28
    else:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28

    if mode == "reg":
        # No dependencies
        p[0] = (struct.pack("<I", p[0]), None)
    else:
        # This instruction cannot be assembled yet: we need to know the label's address
        p[0] = (struct.pack("<I", p[0]), ("addrbranch", plist[-1]))



def p_multiplememinstruction(p):
    """multiplememinstruction : stackinstruction
                              | stmldminstruction"""
    # A multiple memory access instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", p[1]), None)

def p_listregswithpsr(p):
    """listregswithpsr : OPENBRACE LISTREGS CLOSEBRACE
                       | OPENBRACE LISTREGS CLOSEBRACE CARET"""
    plist = list(p)
    p[0] = 0
    if len(p) == 5:
        # PSR and force user bit
        p[0] |= 1 << 22

    # Set the registers
    for i in range(len(plist[2])):
        p[0] |= plist[2][i] << i

def p_stackinstruction(p):
    """stackinstruction : OPMULTIPLEMEM logmnemonic SPACEORTAB listregswithpsr
                        | OPMULTIPLEMEM logmnemonic CONDITION listregswithpsr"""
    global currentMnemonic
    assert currentMnemonic in ("PUSH", "POP")
    plist = list(p)

    p[0] = 1 << 27
    # SP is always used as base register with PUSH and POP
    p[0] |= 13 << 16
    # Write-back
    p[0] |= 1 << 21

    if currentMnemonic == "PUSH":
        # PUSH regs is equivalent to STM SP!, regs
        # Pre-increment
        p[0] |= 1 << 24
    else:   # POP
        # POP regs is equivalent to LDM SP!, regs
        p[0] |= 1 << 20
        # Set mode to UP (add offset)
        p[0] |= 1 << 23

    if len(plist[3].strip()) > 0:
        # We have a condition
        p[0] |= instruction.conditionMapping[plist[3]] << 28
    else:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28

    # Set the registers and optionnally the PSR bit
    p[0] |= plist[-1]

def p_stmldmtargetreg(p):
    """stmldmtargetreg : REG
                       | REG EXCLAMATION"""
    p[0] = p[1] << 16
    if len(p) == 3:
        # Set writeback
        p[0] |= 1 << 21

def p_stmldminstruction(p):
    """stmldminstruction : OPMULTIPLEMEM logmnemonic SPACEORTAB stmldmtargetreg COMMA listregswithpsr
                         | OPMULTIPLEMEM logmnemonic LDMSTMMODE SPACEORTAB stmldmtargetreg COMMA listregswithpsr
                         | OPMULTIPLEMEM logmnemonic CONDITION SPACEORTAB stmldmtargetreg COMMA listregswithpsr
                         | OPMULTIPLEMEM logmnemonic LDMSTMMODE CONDITION SPACEORTAB stmldmtargetreg COMMA listregswithpsr"""
    plist = list(p)
    p[0] = 1 << 27
    # Set base register and write-back
    p[0] |= plist[-3]

    if currentMnemonic == "LDM":
        p[0] |= 1 << 20     # Set load

    conditionSet = False
    modeSet = False
    if len(p) == 8:
        if p[3] in instruction.conditionMapping.keys():
            # Set condition
            p[0] |= instruction.conditionMapping[plist[3]] << 28
            conditionSet = True
        else:
            # Set mode
            mode = plist[3]
            if currentMnemonic == "LDM":
                assert mode in instruction.updateModeLDMMapping
                p[0] |= instruction.updateModeLDMMapping[mode] << 23
            else:   # STM
                assert mode in instruction.updateModeSTMMapping
                p[0] |= instruction.updateModeSTMMapping[mode] << 23
            modeSet = True
    elif len(p) == 9:
        # Set mode
        mode = plist[3]
        if currentMnemonic == "LDM":
            assert mode in instruction.updateModeLDMMapping
            p[0] |= instruction.updateModeLDMMapping[mode] << 23
        else:  # STM
            assert mode in instruction.updateModeSTMMapping
            p[0] |= instruction.updateModeSTMMapping[mode] << 23

        # Set condition
        p[0] |= instruction.conditionMapping[plist[4]] << 28
        conditionSet = True
        modeSet = True

    if not conditionSet:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28

    if not modeSet:
        # Set IA mode
        if currentMnemonic == "LDM":
            p[0] |= instruction.updateModeLDMMapping['IA'] << 23
        else:   # STM
            p[0] |= instruction.updateModeSTMMapping['IA'] << 23

    # Set the registers and optionnally the PSR bit
    p[0] |= plist[-1]


def p_psrinstruction(p):
    """psrinstruction : OPPSR logmnemonic SPACEORTAB REG COMMA PSR
                      | OPPSR logmnemonic SPACEORTAB PSR COMMA REG
                      | OPPSR logmnemonic SPACEORTAB PSR COMMA SHARP CONST
                      | OPPSR logmnemonic CONDITION SPACEORTAB REG COMMA PSR
                      | OPPSR logmnemonic CONDITION SPACEORTAB PSR COMMA REG
                      | OPPSR logmnemonic CONDITION SPACEORTAB PSR COMMA SHARP CONST"""
    global currentMnemonic
    plist = list(p)
    b = 1 << 24

    if currentMnemonic == "MRS":
        assert isinstance(plist[-1], list)
        # Read the PSR
        b |= 0xF << 16
        b |= plist[-3] << 12
        if plist[-1][0] == "SPSR":
            b |= 1 << 22
    else:
        assert isinstance(plist[-3], list)
        # Write the PSR
        b |= 0x28F << 12
        if plist[-1] == '#':
            # Immediate
            raise NotImplementedError()
        else:
            # Register
            b |= plist[-1]
        if plist[-3][0] == "SPSR":
            b |= 1 << 22
        if len(plist[-3]) == 1 or (len(plist[-3]) > 1 and plist[-3][1] != "f"):
            b |= 1 << 16        # Transfer to the whole PSR (not just the flags)

    if len(plist[3].strip()):
        # Set condition
        b |= instruction.conditionMapping[plist[3]] << 28
    else:
        # Set AL condition
        b |= instruction.conditionMapping['AL'] << 28

    # An PSR instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", b), None)


def p_svcinstruction(p):
    """svcinstruction : OPSVC logmnemonic SPACEORTAB CONST
                      | OPSVC logmnemonic SPACEORTAB SHARP CONST
                      | OPSVC logmnemonic CONDITION SPACEORTAB CONST
                      | OPSVC logmnemonic CONDITION SPACEORTAB SHARP CONST"""
    plist = list(p)
    b = 0xF << 24
    b |= plist[-1] & 0xFFFFFF        # 24 bits only
                                        # TODO : add a formal check?

    if len(plist[3].strip()) > 0:
        # Set condition
        b |= instruction.conditionMapping[plist[3]] << 28
    else:
        # Set AL condition
        b |= instruction.conditionMapping['AL'] << 28

    # An SVC/SWI instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", b), None)


def p_multiplyinstruction(p):
    """multiplyinstruction : OPMUL logmnemonic SPACEORTAB REG COMMA REG COMMA REG
                           | OPMUL logmnemonic MODIFYFLAGS SPACEORTAB REG COMMA REG COMMA REG
                           | OPMUL logmnemonic CONDITION SPACEORTAB REG COMMA REG COMMA REG
                           | OPMUL logmnemonic MODIFYFLAGS CONDITION SPACEORTAB REG COMMA REG COMMA REG
                           | OPMUL logmnemonic SPACEORTAB REG COMMA REG COMMA REG COMMA REG
                           | OPMUL logmnemonic MODIFYFLAGS SPACEORTAB REG COMMA REG COMMA REG COMMA REG
                           | OPMUL logmnemonic CONDITION SPACEORTAB REG COMMA REG COMMA REG COMMA REG
                           | OPMUL logmnemonic MODIFYFLAGS CONDITION SPACEORTAB REG COMMA REG COMMA REG COMMA REG"""
    # TODO : factorize these rules
    global currentMnemonic
    plist = list(p)
    p[0] = 9 << 4
    if currentMnemonic == 'MLA':
        p[0] |= 1 << 21
        assert ',' in plist[-6]     # Check if we have 4 registers
        p[0] |= plist[-1] << 12     # Set Rn
        p[0] |= plist[-3] << 8      # Set Rs
        p[0] |= plist[-5]           # Set Rm
        p[0] |= plist[-7] << 16     # Set Rd
    else:
        p[0] |= plist[-1] << 8      # Set Rs
        p[0] |= plist[-3]           # Set Rm
        p[0] |= plist[-5] << 16     # Set Rd

    conditionSet = False
    if plist[3] == 'S':
        # Set flags
        p[0] |= 1 << 20
        if len(plist[4].strip()) > 0:
            # Set condition
            p[0] |= instruction.conditionMapping[plist[4]] << 28
            conditionSet = True
    elif len(plist[3].strip()) > 0:
        # Set condition
        p[0] |= instruction.conditionMapping[plist[3]] << 28
        conditionSet = True

    if not conditionSet:
        p[0] |= instruction.conditionMapping['AL'] << 28

    # A multiply instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", p[0]), None)


# Declarations (with initialization values or with size)

def p_declarationconst(p):
    """declarationconst : CONSTDEC LISTINIT"""
    formatletter = "B" if p[1] == 8 else "H" if p[1] == 16 else "I"  # 32
    bitmask = 2**(p[1]) - 1
    p[0] = (struct.pack("<" + formatletter * len(p[2]), *[v & bitmask for v in p[2]]), None)

def p_declarationsize(p):
    """declarationsize : VARDEC CONST"""
    dimBytes = p[2] * p[1] // 8
    if dimBytes > 8192:
        raise YaccError("Demande d'allocation mémoire trop grande. Le maximum permis est de 8 Ko (8192 octets), mais la déclaration demande {} octets.".format(dimBytes))
    assert dimBytes <= 8192, "Too large memory allocation requested! ({} bytes)".format(dimBytes)
    p[0] = (struct.pack("<" + "B" * dimBytes, *[getSetting("fillValue")] * dimBytes), None)


def p_error(p):
    print("Syntax error in input!")
    print("Wrong data:")
    print(p)
    print("End wrong data")
    return

parser = yacc.yacc()


if __name__ == '__main__':
    a = parser.parse("SECTION INTVEC\n")
    print(a)
    a = parser.parse("  LSR R0, R1, R1\n")
    print(a)
    # print(a, hex(a['BYTECODE']))
    a = parser.parse("\n")
    print(">>>", a, "<<<")
    a = parser.parse("MOV R1, R3, ASR #4\n")
    print(a, hex(a['INSTR']))