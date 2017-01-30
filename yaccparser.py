import struct
import ply.yacc as yacc
from ply.lex import LexToken

from tokenizer import tokens, ParserError, lexer
from settings import getSetting

import instruction

class YaccError(ParserError):
    """
    The exception class used when the lexer encounter an invalid syntax.
    """
    def __init__(self, msg):
        self.msg = msg
        lexer.begin('INITIAL')

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

def p_line_error(p):
    """line : CONST error ENDLINESPACES"""
    raise YaccError("Une étiquette doit commencer par une lettre majuscule ou minuscule (et non pas un chiffre)")

def p_linelabel(p):
    """linelabel : LABEL
                 | LABEL SPACEORTAB COMMENT"""
    p[0] = {'LABEL': p[1]}

def p_linelabel_error(p):
    """linelabel : LABEL error COMMA"""
    raise YaccError("Instruction invalide : \"{}\". Veuillez vous référer au manuel du simulateur pour la liste des instructions acceptées. ".format(p[1]))


def p_sectiondeclaration(p):
    """sectiondeclaration : SECTION SECTIONNAME
                          | SECTION SECTIONNAME SPACEORTAB COMMENT"""
    p[0] = {'SECTION': p[2]}

def p_lineassertion(p):
    """lineassertion : ASSERTION ASSERTIONDATA
                     | ASSERTION ASSERTIONDATA SPACEORTAB COMMENT"""
    p[0] = {'ASSERTION': p[2]}

def p_linedeclaration(p):
    """linedeclaration : LABEL SPACEORTAB declarationconst
                       | LABEL SPACEORTAB declarationconst SPACEORTAB COMMENT
                       | LABEL SPACEORTAB declarationsize
                       | LABEL SPACEORTAB declarationsize SPACEORTAB COMMENT"""
    p[0] = {'LABEL': p[1], 'BYTECODE': p[3]}

def p_lineinstruction(p):
    """lineinstruction : instruction
                       | instruction SPACEORTAB COMMENT"""
    p[0] = {'BYTECODE': p[1]}

def p_linelabelinstr(p):
    """linelabelinstr : LABEL SPACEORTAB instruction
                      | LABEL SPACEORTAB instruction SPACEORTAB COMMENT"""
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


def p_condandspace(p):
    """condandspace : SPACEORTAB
                    | CONDITION SPACEORTAB"""
    cond = instruction.conditionMapping['AL' if len(p) == 2 else p[1]] << 28
    p[0] = cond

def p_flagscondandspace(p):
    """flagscondandspace : MODIFYFLAGS condandspace
                         | condandspace"""
    condandflags = p[1] if len(p) == 2 else p[2]
    if len(p) == 3:
        condandflags |= 1 << 20     # Set flags
    p[0] = condandflags

def p_bytecondandspace(p):
    """bytecondandspace : BYTEONLY condandspace
                        | condandspace"""
    condandbyte = p[1] if len(p) == 2 else p[2]
    if len(p) == 3:
        condandbyte |= 1 << 22      # Set byte mode
    p[0] = condandbyte


def p_datainst2op(p):
    """datainst2op : OPDATA2OP logmnemonic flagscondandspace REG COMMA op2"""
    # We build the instruction bytecode
    # Add the mnemonic
    # We DON'T use p[1] because the op2 rule might have changed it (to fit a constant)!
    b = instruction.dataOpcodeMapping[currentMnemonic] << 21
    # Add the destination register
    b |= p[4] << 12
    # Add the second operand
    b |= p[6]
    # Add the condition and set flags bits
    b |= p[3]
    # We return the bytecode
    p[0] = b

def p_datainst2op_error(p):
    """datainst2op : OPDATA2OP logmnemonic flagscondandspace error COMMA op2
                   | OPDATA2OP logmnemonic flagscondandspace REG error op2
                   | OPDATA2OP logmnemonic flagscondandspace REG error COMMA op2"""

    if len(p) == 8:
        raise YaccError("Le registre R{}{} n'existe pas".format(p[4], p[5].value))
    elif isinstance(p[4], LexToken):
        raise YaccError("L'instruction {} requiert un registre comme premier argument".format(p[1]))
    else:
        raise YaccError("Les registres et/ou constantes utilisés dans une opération doivent être séparés par une virgule")

def p_datainst3op(p):
    """datainst3op : OPDATA3OP logmnemonic flagscondandspace REG COMMA REG COMMA op2"""
    # We build the instruction bytecode
    # Add the mnemonic
    # We DON'T use plist[1] because the op2 rule might have changed it (to fit a constant)!
    b = instruction.dataOpcodeMapping[currentMnemonic] << 21
    # Add the destination register
    b |= p[4] << 12
    # Add the first register operand
    b |= p[6] << 16
    # Add the second operand
    b |= p[8]
    # Add the condition and set flags bits
    b |= p[3]
    # We return the bytecode
    p[0] = b

def p_datainst3op_error(p):
    """datainst3op : OPDATA3OP logmnemonic flagscondandspace REG error REG COMMA op2
                   | OPDATA3OP logmnemonic flagscondandspace REG COMMA REG error op2
                   | OPDATA3OP logmnemonic flagscondandspace REG COMMA REG
                   | OPDATA3OP logmnemonic flagscondandspace REG error COMMA REG COMMA op2
                   | OPDATA3OP logmnemonic flagscondandspace REG COMMA REG error COMMA op2"""
    if len(p) == 9:
        raise YaccError("Les registres et/ou constantes utilisés dans une opération doivent être séparés par une virgule")
    elif len(p) == 7:
        raise YaccError("L'instruction {} requiert 3 arguments".format(p[1]))
    elif len(p) == 10:
        if isinstance(p[5], LexToken):
            raise YaccError("Le registre R{}{} n'existe pas".format(p[4], p[5].value))
        else:
            raise YaccError("Le registre R{}{} n'existe pas".format(p[6], p[7].value))
    elif len(p) == 11:
        raise YaccError("TEST")


def p_datainsttest(p):
    """datainsttest : OPDATATEST logmnemonic condandspace REG COMMA op2"""
    # We build the instruction bytecode
    # Add the mnemonic
    # We DON'T use plist[1] because the op2 rule might have changed it (to fit a constant)!
    b = instruction.dataOpcodeMapping[currentMnemonic] << 21
    # Add the first register operand
    b |= p[4] << 16
    # Add the second operand
    b |= p[6]
    # We always add the S bit
    b |= 1 << 20
    # Set condition
    b |= p[3]
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
    """op2 : REG shift"""
    if len(p) == 3:
        raise YaccError("Le registre R{}{} n'existe pas".format(p[1], p[2].value))
    else:
        raise YaccError("Une virgule est requise avant l'opération de décalage")


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
    """shiftinstrrrx : OPSHIFT logmnemonic flagscondandspace REG COMMA REG"""
    assert p[1] == "RRX"
    p[0] = instruction.shiftMapping[p[1]] << 5
    # Source register
    p[0] |= p[6]
    # Destination register
    p[0] |= p[4] << 12
    # Add the condition and set flags bits
    p[0] |= p[3]



def p_shiftinstrconst(p):
    """shiftinstrconst : OPSHIFT logmnemonic flagscondandspace REG COMMA REG COMMA SHARP CONST"""
    global currentMnemonic
    # Shift mode
    p[0] = instruction.shiftMapping[p[1]] << 5
    # We shift by a constant
    # Destination register
    p[0] |= p[4] << 12
    # Source register
    p[0] |= p[6]
    # Retrieve and check the constant value
    const = p[9]
    assert 0 <= const <= 32
    if not (currentMnemonic in ('LSR', 'ASR') and const == 32):     # Special cases
        p[0] |= const << 7
    # Add the condition and set flags bits
    p[0] |= p[3]



def p_shiftinstrreg(p):
    """shiftinstrreg : OPSHIFT logmnemonic flagscondandspace REG COMMA REG COMMA REG"""
    # Shift mode
    p[0] = instruction.shiftMapping[p[1]] << 5
    # We shift by a register
    p[0] |= 1 << 4
    # Destination register
    p[0] |= p[4] << 12
    # Source register
    p[0] |= p[6]
    # Shift register
    p[0] |= p[8] << 8
    # Add the condition and set flags bits
    p[0] |= p[3]


def p_meminstruction(p):
    """meminstruction : OPMEM logmnemonic bytecondandspace REG COMMA memaccess"""
    global currentMnemonic
    # We build the instruction bytecode
    # Add the mnemonic and the bit signaling this as a memory operation
    p[0] = 1 << 26
    p[0] |= (1 << 20 if currentMnemonic == "LDR" else 0)

    # Add the source/destination register
    p[0] |= p[4] << 12

    # Add the memory access info
    memaccessinfo = p[6]
    p[0] |= memaccessinfo[0]

    # Add the condition and byte mode bits
    p[0] |= p[3]

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
    """branchinstruction : OPBRANCH logmnemonic condandspace LABEL
                         | OPBRANCH logmnemonic condandspace REG"""
    global currentMnemonic
    mode = "reg" if isinstance(p[4], int) else "label"
    # We build the instruction bytecode
    if currentMnemonic == 'BX':
        assert mode == "reg"
        p[0] = 0b000100101111111111110001 << 4
        p[0] |= p[4]
    else:
        assert mode == "label"
        p[0] = 5 << 25
        if currentMnemonic == 'BL':
            p[0] |= 1 << 24

    # Add the condition bits
    p[0] |= p[3]

    if mode == "reg":
        # No dependencies
        p[0] = (struct.pack("<I", p[0]), None)
    else:
        # This instruction cannot be assembled yet: we need to know the label's address
        p[0] = (struct.pack("<I", p[0]), ("addrbranch", p[4]))


def p_branchinstruction_error(p):
    """branchinstruction : OPBRANCH logmnemonic condandspace CONST error"""
    raise YaccError("La cible d'un branchement doit être une étiquette (ou, pour BX, un registre). Une étiquette ne peut pas commencer par un chiffre.")


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
    """stackinstruction : OPMULTIPLEMEM logmnemonic condandspace listregswithpsr"""
    global currentMnemonic
    assert currentMnemonic in ("PUSH", "POP")

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

    # Add the condition bits
    p[0] |= p[3]

    # Set the registers and optionnally the PSR bit
    p[0] |= p[4]

def p_stmldmtargetreg(p):
    """stmldmtargetreg : REG
                       | REG EXCLAMATION"""
    p[0] = p[1] << 16
    if len(p) == 3:
        # Set writeback
        p[0] |= 1 << 21

def p_stmldminstruction(p):
    """stmldminstruction : OPMULTIPLEMEM logmnemonic condandspace stmldmtargetreg COMMA listregswithpsr
                         | OPMULTIPLEMEM logmnemonic LDMSTMMODE condandspace stmldmtargetreg COMMA listregswithpsr"""
    plist = list(p)
    p[0] = 1 << 27
    # Set base register and write-back
    p[0] |= plist[-3]

    if currentMnemonic == "LDM":
        p[0] |= 1 << 20     # Set load

    if len(p) == 8:
        # We have an explicit mode
        mode = p[3]
        if currentMnemonic == "LDM":
            assert mode in instruction.updateModeLDMMapping
            p[0] |= instruction.updateModeLDMMapping[mode] << 23
        else:  # STM
            assert mode in instruction.updateModeSTMMapping
            p[0] |= instruction.updateModeSTMMapping[mode] << 23

        # Add the condition bits
        p[0] |= p[4]
    else:
        # Set IA mode
        if currentMnemonic == "LDM":
            p[0] |= instruction.updateModeLDMMapping['IA'] << 23
        else:  # STM
            p[0] |= instruction.updateModeSTMMapping['IA'] << 23

        # Add the condition bits
        p[0] |= p[3]

    # Set the registers and optionnally the PSR bit
    p[0] |= plist[-1]


def p_psrinstruction(p):
    """psrinstruction : OPPSR logmnemonic condandspace REG COMMA PSR
                      | OPPSR logmnemonic condandspace PSR COMMA REG
                      | OPPSR logmnemonic condandspace PSR COMMA SHARP CONST"""
    global currentMnemonic
    b = 1 << 24

    if currentMnemonic == "MRS":
        assert isinstance(p[6], list)
        # Read the PSR
        b |= 0xF << 16
        b |= p[4] << 12
        if p[6][0] == "SPSR":
            b |= 1 << 22
    else:
        assert isinstance(p[4], list)
        # Write the PSR
        b |= 0x28F << 12
        if p[6] == '#':
            # Immediate
            raise NotImplementedError()
        else:
            # Register
            b |= p[6]
        if p[4][0] == "SPSR":
            b |= 1 << 22
        if len(p[4]) == 1 or (len(p[4]) > 1 and p[4][1] != "f"):
            b |= 1 << 16        # Transfer to the whole PSR (not just the flags)

    # Add the condition bits
    b |= p[3]

    # An PSR instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", b), None)


def p_svcinstruction(p):
    """svcinstruction : OPSVC logmnemonic condandspace CONST
                      | OPSVC logmnemonic condandspace SHARP CONST"""
    plist = list(p)
    b = 0xF << 24
    b |= plist[-1] & 0xFFFFFF        # 24 bits only
                                     # TODO : add a formal check?
    # Add the condition bits
    b |= p[3]

    # An SVC/SWI instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", b), None)


def p_multiplyinstruction(p):
    """multiplyinstruction : OPMUL logmnemonic flagscondandspace REG COMMA REG COMMA REG
                           | OPMUL logmnemonic flagscondandspace REG COMMA REG COMMA REG COMMA REG"""
    global currentMnemonic
    p[0] = 9 << 4
    if currentMnemonic == 'MLA':
        p[0] |= 1 << 21
        assert len(p) == 11         # Check if we have 4 registers
        p[0] |= p[10] << 12         # Set Rn
        p[0] |= p[8] << 8           # Set Rs
        p[0] |= p[6]                # Set Rm
        p[0] |= p[4] << 16          # Set Rd
    else:
        p[0] |= p[8] << 8           # Set Rs
        p[0] |= p[6]                # Set Rm
        p[0] |= p[4] << 16          # Set Rd

    # Add the condition bits
    p[0] |= p[3]

    # A multiply instruction is always complete (e.g. it never depends on the location of a label),
    # so we just pack it in a bytes object
    p[0] = (struct.pack("<I", p[0]), None)


# Declarations (with initialization values or with size)

def p_declarationconst(p):
    """declarationconst : CONSTDEC LISTINIT"""
    if p[1] not in (8, 16, 32):
        raise YaccError("Une constante peut avoir les tailles suivantes (en bits) : 8, 16 ou 32. {} n'est pas une taille valide".format(p[1]))
    formatletter = "B" if p[1] == 8 else "H" if p[1] == 16 else "I"  # 32
    bitmask = 2**(p[1]) - 1
    p[0] = (struct.pack("<" + formatletter * len(p[2]), *[v & bitmask for v in p[2]]), None)

def p_declarationconst_error(p):
    """declarationsize : CONSTDECWITHOUTSIZE CONST"""
    raise YaccError("Une déclaration de constante doit être suivie d'une taille en bits (par exemple DC32 ou DC8)")

def p_declarationsize(p):
    """declarationsize : VARDEC CONST"""
    if p[1] not in (8, 16, 32):
        raise YaccError("Une variable peut avoir les tailles suivantes (en bits) : 8, 16 ou 32. {} n'est pas une taille valide".format(p[1]))
    dimBytes = p[2] * p[1] // 8
    if dimBytes > 8192:
        raise YaccError("Demande d'allocation mémoire trop grande. Le maximum permis est de 8 Ko (8192 octets), mais la déclaration demande {} octets.".format(dimBytes))
    assert dimBytes <= 8192, "Too large memory allocation requested! ({} bytes)".format(dimBytes)
    p[0] = (struct.pack("<" + "B" * dimBytes, *[getSetting("fillValue")] * dimBytes), None)

def p_declarationsize_error(p):
    """declarationsize : VARDECWITHOUTSIZE CONST"""
    raise YaccError("Une déclaration de variable doit être suivie d'une taille en bits (par exemple DS32 ou DS8)")


#def p_error(p):
#    print("Syntax error in input!")
#    print("Wrong data:")
#    print(p)
#    print("End wrong data")
#    return

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