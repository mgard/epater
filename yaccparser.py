import struct
import ply.yacc as yacc

from tokenizer import tokens, ParserError

import instruction


currentMnemonic = ""

def p_line(p):
    """line : COMMENT ENDLINESPACES
            | linelabel ENDLINESPACES
            | linelabelinstr ENDLINESPACES
            | lineinstruction ENDLINESPACES
            | sectiondeclaration ENDLINESPACES
            | linedeclaration ENDLINESPACES"""
    p[0] = p[1]

def p_linelabel(p):
    """linelabel : LABEL
                 | LABEL COMMENT"""
    p[0] = {'LABEL': p[1]}

def p_sectiondeclaration(p):
    """sectiondeclaration : SECTION SECTIONNAME
                          | SECTION SECTIONNAME COMMENT"""
    p[0] = {'SECTION': p[2]}

def p_linedeclaration(p):
    """linedeclaration : LABEL SPACEORTAB CONSTDEC LISTINIT
                       | LABEL SPACEORTAB CONSTDEC LISTINIT COMMENT
                       | LABEL SPACEORTAB VARDEC CONST
                       | LABEL SPACEORTAB VARDEC CONST COMMENT"""
    p[0] = {'LABEL': p[1], 'DECLARATION': (p[3], p[4])}

def p_lineinstruction(p):
    """lineinstruction : instruction
                       | instruction COMMENT"""
    p[0] = {'INSTR': p[1]}

def p_linelabelinstr(p):
    """linelabelinstr : LABEL SPACEORTAB instruction
                      | LABEL SPACEORTAB instruction COMMENT"""
    p[0] = {'LABEL': p[1], 'INSTR': p[3]}

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
    """datainst2op : OPDATA2OP error REG"""
    print("PAF")

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
            assert False        # TODO : generate error, unable to encode constant
        immval, immrot, inverse = ret
        if inverse and currentMnemonic not in instruction.dataOpcodeInvert.keys():
            assert False        # We could fit the constant by inverting it, but we do not have invert operation for this mnemonic
        elif inverse:
            # We switch the mnemonic
            currentMnemonic = instruction.dataOpcodeInvert[currentMnemonic]
        # We encode the shift
        p[0] |= immval
        p[0] |= immrot << 8
    elif len(plist) == 4:
        # Shifted register
        p[0] = plist[1]
        p[0] |= plist[3] << 4

def p_op2_error(p):
    """op2 : error"""
    print("BOUM")

def p_shift(p):
    """shift : INNERSHIFT
             | INNERSHIFT SPACEORTAB REG
             | INNERSHIFT SPACEORTAB SHARP CONST"""
    plist = list(p)
    # Shift type
    p[0] = instruction.shiftMapping[p[1]] << 5
    if len(plist) == 2:
        # Special case, must be RRX
        assert p[1] == "RRX"
    elif len(plist) == 3:
        # Shift by register
        p[0] |= 1 << 4
        p[0] |= p[3] << 8
    elif not (p[1] in ('LSR', 'ASR') and p[4] == 32):
        # Shift by a constant if we are not in special modes
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
    p[0] = (struct.pack("<I", p[1]), None)

def p_shiftinstrrrx(p):
    """shiftinstrrrx : OPSHIFT logmnemonic SPACEORTAB REG COMMA REG
                     | OPSHIFT logmnemonic MODIFYFLAGS SPACEORTAB REG COMMA REG
                     | OPSHIFT logmnemonic CONDITION SPACEORTAB REG COMMA REG
                     | OPSHIFT logmnemonic MODIFYFLAGS CONDITION SPACEORTAB REG COMMA REG"""
    plist = list(p)
    assert p[1] == "RRX"
    p[0] = instruction.shiftMapping[p[1]] << 5
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
    plist = list(p)
    # Shift mode
    p[0] = instruction.shiftMapping[p[1]] << 5
    # We shift by a constant
    # Destination register
    p[0] |= plist[-5] << 12
    # Source register
    p[0] |= plist[-3]
    # Retrieve and check the constant value
    const = plist[-1]
    assert 0 <= const <= 32
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
            if plist[5] > 0:
                p[0] |= 1 << 23
            offset = abs(plist[5])
            if offset > 2**12-1:
                assert False        # Cannot encode the offset
            p[0] |= offset & 0xFFF
        else:                   # Register offset
            p[0] |= plist[4]
            if ',' in plist[5]:     # We have a shift
                p[0] |= plist[6]

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
            assert False        # Cannot encode the offset
        p[0] |= offset & 0xFFF
    else:                   # Register offset
        p[0] |= plist[5]
        if len(plist) > 7:  # We have a shift
            p[0] |= plist[7]

    p[0] = (p[0], None)     # No external dependencies (this instruction is self contained, no reference to labels)

def p_memaccesslabel(p):
    """memaccesslabel : LABEL"""
    p[0] = (0, ("addr", p[1]))     # This instruction cannot be assembled yet: we need to know the label's address

def p_memaccesslabeladdr(p):
    """memaccesslabeladdr : EQUALS LABEL"""
    p[0] = (0, ("addrptr", p[1]))     # This instruction cannot be assembled yet: we need to know the label's address


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

    conditionSet = False
    if len(p) == 7:
        if p[3] in instruction.conditionMapping.keys():
            # Set condition
            p[0] |= instruction.conditionMapping[plist[3]] << 28
        else:
            # Set mode
            if currentMnemonic == "LDM":
                assert plist[3] in instruction.updateModeLDMMapping
                p[0] |= instruction.updateModeLDMMapping[plist[3]] << 28
            else:   # STM
                assert plist[3] in instruction.updateModeSTMMapping
                p[0] |= instruction.updateModeSTMMapping[plist[3]] << 28
    elif len(p) == 8:
        # Set mode
        if currentMnemonic == "LDM":
            assert plist[3] in instruction.updateModeLDMMapping
            p[0] |= instruction.updateModeLDMMapping[plist[3]] << 28
        else:  # STM
            assert plist[3] in instruction.updateModeSTMMapping
            p[0] |= instruction.updateModeSTMMapping[plist[3]] << 28

        # Set condition
        p[0] |= instruction.conditionMapping[plist[4]] << 28
        conditionSet = True

    if not conditionSet:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28

    # Set the registers and optionnally the PSR bit
    p[0] |= plist[-1]


def p_psrinstruction(p):
    """psrinstruction : OPPSR logmnemonic SPACEORTAB REG COMMA PSR
                      | OPPSR logmnemonic SPACEORTAB PSR COMMA REG
                      | OPPSR logmnemonic CONDITION SPACEORTAB REG COMMA PSR
                      | OPPSR logmnemonic CONDITION SPACEORTAB PSR COMMA REG"""
    plist = list(p)
    p[0] = 1 << 24
    
    # TODO

    if len(plist) > 7:
        # Set condition
        p[0] |= instruction.conditionMapping[plist[3]] << 28
    else:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28


def p_svcinstruction(p):
    """svcinstruction : OPSVC logmnemonic SPACEORTAB CONST
                      | OPSVC logmnemonic SPACEORTAB SHARP CONST
                      | OPSVC logmnemonic CONDITION SPACEORTAB CONST
                      | OPSVC logmnemonic CONDITION SPACEORTAB SHARP CONST"""
    plist = list(p)
    p[0] = 0xF << 24
    p[0] |= plist[-1] & 0xFFFFFF        # 24 bits only
                                        # TODO : add a formal check?

    if len(plist) > 4 and plist[3] != "#":
        # Set condition
        p[0] |= instruction.conditionMapping[plist[3]] << 28
    else:
        # Set AL condition
        p[0] |= instruction.conditionMapping['AL'] << 28


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
    plist = list(p)
    p[0] = 9 << 4
    # TODO

def p_error(p):
    print(p)
    print("Syntax error in input!")

parser = yacc.yacc()


if __name__ == '__main__':
    a = parser.parse("MOVinterne MOV R1, #15\n")
    print(a, hex(a['INSTR']))
    a = parser.parse("MOV R1, R3, ASR #4\n")
    print(a, hex(a['INSTR']))