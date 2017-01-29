import re
from collections import namedtuple
from itertools import chain
import ply.lex as lex

import instruction as instrInfos

"""
This is the lexer definiton for the ARM assembly parser.
It was not designed with performance in mind, but to ease its usage. In particular :
- It must be able to return meaningful error messages
- It must tolerate "acceptable" deviations to canonical assembly. For example, this parser does not require the
    instructions to be indented compared to the labels
- However, it must NOT allow a construction that can mislead the user. For instance, allowing the use of "XOR" as
    label is misleading because one could think that this is actually an instruction (which is not).

This lexer is structured around _conditional lexing_ (see http://www.dabeaz.com/ply/ply.html#ply_nn21 for more
information). Each line is independently considered. When the parser encounters a mnemonic, it enters a special state,
where suffixes are allowed. For instance, with data operation, 'S' is an allowed suffixes (to set the flags), along
with the usual conditional suffixes. With LDR/STR, 'B' and 'H' are allowed, but not 'S', and so on.
Once the parser reaches a space (or tab) character in this mode, it switches to instruction mode. In this mode, the
available tokens are only the ones that are allowed. For instance, a data instruction does not allow memory acces
(with [ and ]), so these characters trigger an error. At the end of each line, the state of the lexer is reset.
"""


states = (
    ('dataopcode', 'exclusive'),
    ('cmpopcode', 'exclusive'),
    ('shiftopcode', 'exclusive'),
    ('memopcode', 'exclusive'),
    ('multiplememopcode', 'exclusive'),
    ('branchopcode', 'exclusive'),
    ('psropcode', 'exclusive'),
    ('mulopcode', 'exclusive'),
    ('svcopcode', 'exclusive'),
    ('generalopcode', 'exclusive'),

    ('datainstr', 'exclusive'),
    ('cmpinstr', 'exclusive'),
    ('shiftinstr', 'exclusive'),
    ('meminstr', 'exclusive'),
    ('multiplememinstr', 'exclusive'),
    ('branchinstr', 'exclusive'),
    ('psrinstr', 'exclusive'),
    ('mulinstr', 'exclusive'),
    ('svcinstr', 'exclusive'),
    ('generalinstr', 'exclusive'),

    ('decwithsize', 'exclusive'),
    ('decwithvalues', 'exclusive'),
    ('section', 'exclusive'),
    ('assertion', 'exclusive'),
)

tokens = (
   'COMMENT',
   'SECTION',
   'SECTIONNAME',
   'ASSERTION',
   'ASSERTIONDATA',
   'CONSTDEC',
   'VARDEC',
   'SPACEORTAB',
   'ENDLINESPACES',
   'STARTSPACES',
   'COMMA',
   'SHARP',
   'OPENBRACKET',
   'CLOSEBRACKET',
   'OPENBRACE',
   'CLOSEBRACE',
   'CARET',
   'EXCLAMATION',
   'CONDITION',
   'BYTEONLY',
   'HALFONLY',
   'MODIFYFLAGS',
   'LDMSTMMODE',
   'PSR',
   'REG',
   'LISTREGS',
   'CONST',
   'LISTINIT',
   'INNERSHIFT',
   'OPDATA2OP',
   'OPDATA3OP',
   'OPDATATEST',
   'OPMEM',
   'OPMULTIPLEMEM',
   'OPSHIFT',
   'OPBRANCH',
   'OPPSR',
   'OPSVC',
   'OPMUL',
   'LABEL',
   'EQUALS',
   'RANGE',
)

class ParserError(Exception):
    """
    Generic class for all lexer/parser errors.
    """

class LexError(ParserError):
    """
    The exception class used when the lexer encounter an invalid syntax.
    """
    def __init__(self, msg):
        self.msg = msg
        lexer.begin('INITIAL')

    def __str__(self):
        return self.msg

# A comment is always a comment
def t_ANY_COMMENT(t):
    r';.*$'
    t.lexer.begin('INITIAL')
    return t

# A new line resets the state
def t_ANY_ENDLINESPACES(t):
    r'(?<=\S)\s*$'
    t.lexer.begin('INITIAL')
    return t

# A section declaration
def t_SECTION(t):
    r'SECTION\s+'
    t.lexer.begin('section')
    return t

def t_section_SECTIONNAME(t):
    r'\w+'
    return t

def t_ASSERTION(t):
    r'ASSERT\s+'
    t.lexer.begin('assertion')
    return t

def t_assertion_ASSERTIONDATA(t):
    r'(\s*(R1[0-5]|R[0-9]|SP|LR|PC|C|Z|V|N|0x[0-9a-fA-F]+)=[+-]?(0x[0-9a-fA-F]+|[0-9]+),?)+'
    return t

# A constant or variable declaration
def t_CONSTDEC(t):
    r'(?<=[\t ])DC(8|16|32)\s+'
    t.lexer.begin('decwithvalues')
    t.value = int(t.value[2:])
    return t

def t_VARDEC(t):
    r'(?<=[\t ])DS(8|16|32)\s+'
    t.lexer.begin('decwithsize')
    t.value = int(t.value[2:])
    return t


# A data operation (2 operands)
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join(("MOV", "MVN")) + r'(?=[A-Z\t ]))')
def t_OPDATA2OP(t):
    t.lexer.begin('dataopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.dataop
    t.lexer.expectedArgs = 2
    t.lexer.suffixesSeen = set()
    return t

# A data operation (3 operands)
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join(("AND", "EOR", "SUB", "RSB", "ADD", "ADC", "SBC", "RSC", "ORR", "BIC")) + r'(?=[A-Z\t ]))')
def t_OPDATA3OP(t):
    t.lexer.begin('dataopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.dataop
    t.lexer.expectedArgs = 3
    t.lexer.suffixesSeen = set()
    return t

# May or may not set the flags
def t_dataopcode_shiftopcode_mulopcode_MODIFYFLAGS(t):
    r'S'
    if 'S' in t.lexer.suffixesSeen:
        assert False, "More than one occurrence of setflags mode!"
    t.lexer.suffixesSeen.add(t.value)
    return t

# We transition into the instruction arguments
def t_dataopcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('datainstr')
    return t


# A comparison operation
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join(("CMP", "CMN", "TST", "TEQ")) + r'(?=[A-Z\t ]))')
def t_OPDATATEST(t):
    t.lexer.begin('cmpopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.dataop
    t.lexer.expectedArgs = 2
    t.lexer.suffixesSeen = set()
    return t

# We transition into the instruction arguments
def t_cmpopcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('cmpinstr')
    return t


# A shift operation
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.shiftop])+r'(?=[A-Z\t ]))')
def t_OPSHIFT(t):
    t.lexer.begin('shiftopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.shiftop
    t.lexer.expectedArgs = 3
    t.lexer.suffixesSeen = set()
    return t

# We transition into the instruction arguments
def t_shiftopcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('shiftinstr')
    return t


# A memory operation
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.memop])+r'(?=[A-Z\t ]))')
def t_OPMEM(t):
    t.lexer.begin('memopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.memop
    t.lexer.expectedArgs = 2
    t.lexer.suffixesSeen = set()
    return t

def t_memopcode_BYTEONLY(t):
    r'B'
    if 'B' in t.lexer.suffixesSeen or 'H' in t.lexer.suffixesSeen:
        assert False, "Only one byte/half mode!"
    t.lexer.suffixesSeen.add(t.value)
    return t

def t_memopcode_HALFONLY(t):
    r'H'
    if 'B' in t.lexer.suffixesSeen or 'H' in t.lexer.suffixesSeen:
        assert False, "Only one byte/half mode!"
    t.lexer.suffixesSeen.add(t.value)
    return t

# We transition into the instruction arguments
def t_memopcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('meminstr')
    return t


# A multiple memory operation
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.multiplememop])+r'(?=[A-Z\t ]))')
def t_OPMULTIPLEMEM(t):
    t.lexer.begin('multiplememopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.multiplememop
    t.lexer.expectedArgs = 2
    t.lexer.suffixesSeen = set()
    return t

@lex.TOKEN(r'(' + "|".join(chain(instrInfos.updateModeLDMMapping.keys(), instrInfos.updateModeSTMMapping.keys()))+')')
def t_multiplememopcode_LDMSTMMODE(t):
    for elem in t.lexer.suffixesSeen:
        if elem in chain(instrInfos.updateModeLDMMapping.keys(), instrInfos.updateModeSTMMapping.keys()):
            assert False, "Only one multiple load mode!"
    t.lexer.suffixesSeen.add(t.value)
    return t

# We transition into the instruction arguments
def t_multiplememopcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('multiplememinstr')
    return t


# A branch operation
# We do not use the keys from exportInstrInfo, because the order is important: the longest mnemonics must
# be at the beginning, or else the previous (shorter) ones would match them!
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join(("BLX", "BL", "BX", "B"))+r'(?=[A-Z\t ]))')
def t_OPBRANCH(t):
    t.lexer.begin('branchopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.branch
    t.lexer.expectedArgs = 1
    t.lexer.suffixesSeen = set()
    return t

# We transition into the instruction arguments
def t_branchopcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('branchinstr')
    return t


# A read/write to PSR
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.psrtransfer])+r'(?=[A-Z\t ]))')
def t_OPPSR(t):
    t.lexer.begin('psropcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.psrtransfer
    t.lexer.expectedArgs = 2
    t.lexer.suffixesSeen = set()
    return t

# We transition into the instruction arguments
def t_psropcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('psrinstr')
    return t


# A multiplication
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.multiply])+r'(?=[A-Z\t ]))')
def t_OPMUL(t):
    t.lexer.begin('mulopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.multiply
    t.lexer.expectedArgs = 3
    t.lexer.suffixesSeen = set()
    return t

# We transition into the instruction arguments
def t_mulopcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('mulinstr')
    return t


# SVC/SWI
@lex.TOKEN(r'(' + r'(?=[A-Z\t ])|'.join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.softinterrupt])+r'(?=[A-Z\t ]))')
def t_OPSVC(t):
    t.lexer.begin('svcopcode')
    t.lexer.currentMnemonic = t.value
    t.lexer.countArgs = 0
    t.lexer.instrType = instrInfos.InstrType.softinterrupt
    t.lexer.expectedArgs = 1
    t.lexer.suffixesSeen = set()
    return t

# We transition into the instruction arguments
def t_svcopcode_SPACEORTAB(t):
    r'[ \t]+'
    t.lexer.begin('svcinstr')
    return t



# An instruction can be conditionnal
@lex.TOKEN(r'(' + "|".join(instrInfos.conditionMapping.keys())+')')
def t_dataopcode_shiftopcode_cmpopcode_memopcode_multiplememopcode_branchopcode_psropcode_mulopcode_svcopcode_generalopcode_CONDITION(t):
    for elem in t.lexer.suffixesSeen:
        if elem in instrInfos.conditionMapping.keys():
            assert False, "Only one condition!"
    t.lexer.suffixesSeen.add(t.value)
    return t

# Must come _before_ REG rule
def t_multiplememinstr_LISTREGS(t):
    r'(?<={)(R1[0-5]|R[0-9]|SP|LR|PC|-|,|\s)+(?=})'
    listRegs = [0] * 16
    val = t.value.replace(" ", "").replace("\t", "").replace("LR", "R14").replace("PC", "R15").replace("SP", "R13")
    baseRegsPos = [i for i in range(len(val)) if val[i] == "R"]
    baseRegsEndPos = []
    regs = []
    for i in baseRegsPos:
        j = i + 1
        regs.append("")
        while j < len(val) and val[j].isdigit():
            regs[-1] += val[j]
            j += 1
        regs[-1] = int(regs[-1])
        baseRegsEndPos.append(j)
    for i, (r, end) in enumerate(zip(regs, baseRegsEndPos)):
        if end == len(val) or val[end] == ',':
            listRegs[r] = 1
        elif val[end] == '-':
            for j in range(r, regs[i + 1]):  # Last register not included
                listRegs[j] = 1
    t.value = listRegs
    return t


# PSR transfer might use CPSR or SPSR, with an optionnal suffix
# Must be before REG rule, because else SPSR will be parsed as "SP + SR"
def t_psrinstr_PSR(t):
    r'(SPSR|CPSR)(_cxsf|_flg|_all|_f)?'
    t.value = t.value.split("_")
    return t

# These kinds of instructions may contains register as argument :
# - Data instructions
# - Shift instructions
# - Comparison instructions
# - Memory acesses
# - Multiple memory accesses
# - Branches (with BX)
def t_ANY_REG(t):
    r'(R1[0-5]|R[0-9]|SP|LR|PC)'
    if t.value[0] != 'R':
        t.value = {'SP': 13, 'LR': 14, 'PC': 15}[t.value]
    else:
        t.value = int(t.value[1:])
    t.lexer.countArgs += 1
    return t


# The constant declaration (DC) is the only case where we may have multiple constants on the same line
def t_decwithvalues_LISTINIT(t):
    r'([+-]?(\s*0x[0-9a-fA-F]+|[0-9]+),?)+'
    valsStr = t.value.split(",")
    valsInt = []
    for v in valsStr:
        v = v.strip().lower()
        valsInt.append(int(v, 16) if '0x' in v else int(v))
    t.value = valsInt
    return t


# To declare a constant
t_ANY_SHARP = r'\#'
def t_ANY_CONST(t):
    r'[+-]?(0x[0-9a-fA-F]+|[0-9]+)'
    t.value = int(t.value.strip(), 16) if '0x' in t.value.lower() else int(t.value.strip())
    t.lexer.countArgs += 1
    return t

def t_datainstr_cmpinstr_meminstr_INNERSHIFT(t):
    r'(LSL|LSR|ASR|ROR|RRX)'
    return t


# A branch cannot contain a comma
#t_datainstr_shiftinstr_cmpinstr_meminstr_multiplememinstr_psrinstr_mulinstr_decwithvalues_COMMA = r'[\t ]*,[\t ]*'
t_ANY_COMMA = r'[\t ]*,[\t ]*'

# Only memory instructions may have brackets
t_meminstr_OPENBRACKET = r'\['
t_meminstr_CLOSEBRACKET = r'\]'
t_meminstr_multiplememinstr_EXCLAMATION = r'!'
t_meminstr_EQUALS = r'='

# Only multiple mem instructions may have braces
t_multiplememinstr_OPENBRACE = r'{'
t_multiplememinstr_CLOSEBRACE = r'}'
t_multiplememinstr_CARET = r'\^'
t_multiplememinstr_RANGE = r'-'

t_ignore_ANY_STARTSPACES = r'^([ \t]*(?=\w+)|(?=\w+))'
t_ANY_SPACEORTAB = r'[ \t]+'

# A label can be :
# - Alone, at the beginning of a line
# - A branch target
# - A load/store target
def t_INITIAL_branchinstr_meminstr_LABEL(t):
    r'\w+'
    if hasattr(t.lexer, 'countArgs'):
        t.lexer.countArgs += 1
    return t

# Error handlers
def t_section_error(t):
    print("(01) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_decwithsize_error(t):
    print("(02) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_decwithvalues_error(t):
    print("(03) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_dataopcode_error(t):
    print("(04) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_cmpopcode_error(t):
    print("(05) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_shiftopcode_error(t):
    print("(06) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_memopcode_error(t):
    print("(07) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_multiplememopcode_error(t):
    print("(08) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_branchopcode_error(t):
    print("(09) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_psropcode_error(t):
    print("(10) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_mulopcode_error(t):
    print("(11) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_svcopcode_error(t):
    print("(12) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_generalopcode_error(t):
    print("(13) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))


def t_datainstr_error(t):
    print(t.lexer.countArgs)
    print("(14) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_cmpinstr_error(t):
    print("(15) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_shiftinstr_error(t):
    print("(16) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_meminstr_error(t):
    print("(17) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_multiplememinstr_error(t):
    print("(18) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_branchinstr_error(t):
    print("(19) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_psrinstr_error(t):
    print("(20) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_mulinstr_error(t):
    print("(21) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_svcinstr_error(t):
    print("(22) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

def t_generalinstr_error(t):
    print("(23) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))

# General handler
def t_error(t):
    print("(G) Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))
    #print("Illegal character '%s'" % t.value[0])
    #t.lexer.skip(1)

lexer = lex.lex()


if __name__ == "__main__":
    a = lexer.input("MOV R1, R2\n")
    print(lexer.token(), lexer.token(), lexer.token(), lexer.token(),lexer.token(), lexer.token(), lexer.token())