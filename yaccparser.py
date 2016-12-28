import re
from collections import namedtuple
import ply.yacc as yacc

from tokenizer import tokens

from instruction import exportInstrInfo

"""
Grammar definition

instruction : opcodemem reg , memaccess
            | opcodedata2 reg , reg, operandshift
            | opcodedata1 reg , operandshift
            |
"""


class LexError(Exception):
    """
    The exception class used when the parser encounter an invalid syntax.
    """
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

DummyToken = namedtuple("DummyToken", ['type', 'value'])
DecInfo = namedtuple("DecInfo", ['type', 'nbits', 'dim', 'vals'])
ShiftInfo = namedtuple("ShiftInfo", ['type', 'count'])
MemAccessPostInfo = namedtuple("MemAccessPostInfo", ['base', 'offsettype', 'offset', 'direction'])
MemAccessPreInfo = namedtuple("MemAccessPretInfo", ['base', 'offsettype', 'offset', 'direction', 'shift'])


ConditionInfo = namedtuple("ConditionInfo", 'cond')


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
    """linedeclaration : LABEL CONSTDEC LISTINIT
                       | LABEL CONSTDEC LISTINIT COMMENT
                       | LABEL VARDEC CONST
                       | LABEL VARDEC CONST COMMENT"""
    p[0] = {'DECLARATION': (p[1], p[2], p[3])}

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
                   | shiftinstruction"""
    p[0] = p[1]

def p_datainstruction(p):
    """datainstruction : datainst2op
                       | datainst3op
                       | datainsttest"""
    p[0] = p[1]

def p_datainst2op(p):
    """datainst2op : OPDATA2OP SPACEORTAB REG COMMA op2
                   | OPDATA2OP CONDITION SPACEORTAB REG COMMA op2
                   | OPDATA2OP MODIFYFLAGS SPACEORTAB REG COMMA op2
                   | OPDATA2OP MODIFYFLAGS CONDITION SPACEORTAB REG COMMA op2"""
    plist = list(p)
    d = {}
    d['op'] = plist[1]
    d['rd'] = plist[-3]
    d['op2'] = plist[-1]
    d['suffixes'] = []
    if len(plist) == 7:
        if plist[2] == 'S':
            d['suffixes'].append(("setflags", True))
        else:
            d['suffixes'].append(("condition", plist[2]))
    if len(plist) == 8:
        d['suffixes'].append(("setflags", True))
        d['suffixes'].append(("condition", plist[3]))
    p[0] = d

def p_datainst2op_error(p):
    """datainst2op : OPDATA2OP error REG"""
    print("PAF")

def p_datainst3op(p):
    """datainst3op : OPDATA3OP SPACEORTAB REG COMMA REG COMMA op2
                   | OPDATA3OP CONDITION SPACEORTAB REG COMMA REG COMMA op2
                   | OPDATA3OP MODIFYFLAGS SPACEORTAB REG COMMA REG COMMA op2
                   | OPDATA3OP MODIFYFLAGS CONDITION SPACEORTAB REG COMMA REG COMMA op2"""
    print("3!!!!!")
    p[0] = p[1]

def p_datainsttest(p):
    """datainsttest : OPDATATEST SPACEORTAB REG COMMA op2
                    | OPDATATEST CONDITION SPACEORTAB REG COMMA op2"""
    print("3!!!!!")
    p[0] = p[1]

def p_op2(p):
    """op2 : REG
           | SHARP CONST
           | REG COMMA shift"""
    plist = list(p)
    if len(plist) == 2:
        # Register only
        p[0] = ("Register", plist[1], ShiftInfo(type="LSL", count=0))
    elif len(plist) == 3:
        # Constant
        p[0] = ("Constant", plist[2])
    elif len(plist) == 4:
        # Shifted register
        p[0] = ("Register", plist[1], plist[3])

def p_op2_error(p):
    """op2 : error"""
    print("BOUM")

def p_shift(p):
    """shift : INNERSHIFT SHARP CONST"""
    plist = list(p)
    p[0] = ShiftInfo(type=plist[1], count=plist[3])


def p_meminstruction(p):
    """meminstruction : OPMEM SPACES REG COMMA memaccess
                      | OPMEM CONDITION SPACES REG COMMA memaccess
                      | OPMEM BYTEONLY SPACES REG COMMA memaccess
                      | OPMEM BYTEONLY CONDITION SPACES REG COMMA memaccess"""
    p[0] = "MEM"

def p_memaccess(p):
    """memaccess : OPENBRACKET REG CLOSEBRACKET
                 | OPENBRACKET REG COMMA REG CLOSEBRACKET
                 | OPENBRACKET REG COMMA REG CLOSEBRACKET EXCLAMATION
                 | OPENBRACKET REG COMMA SHARP CONST CLOSEBRACKET"""
    p[0] = "MEMACCESS"

def p_branchinstruction(p):
    """branchinstruction : OPBRANCH LABEL
                         | OPBRANCH REG"""
    print("Branch!")
    p[0] = "BRANCH"

def p_multiplememinstruction(p):
    """multiplememinstruction : OPMULTIPLEMEM OPENBRACE REG CLOSEBRACE
                              | OPMULTIPLEMEM REG COMMA OPENBRACE REG CLOSEBRACE"""
    p[0] = "MULTIPLEMEM"

def p_shiftinstruction(p):
    """shiftinstruction : OPSHIFT SPACES REG COMMA REG COMMA REG
                        | OPSHIFT SPACES REG COMMA REG COMMA SHARP CONST"""
    p[0] = "SHIFT"


def p_error(p):
    print(p)
    print("Syntax error in input!")

parser = yacc.yacc()


if __name__ == '__main__':
    a = parser.parse("MOVinterne MOVEQ R1, R3\n")
    print(a)
    a = parser.parse("MOV R1, R3\n")
    print(a)