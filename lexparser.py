import re
from collections import namedtuple
import ply.lex as lex


instructionList = ['MOV', 'LDR', 'STR', 'LDM', 'STM', 'ADD', 'SUB', 'POP', 'PUSH', 'B']
regexpInstr = (r'|').join(instructionList)

DecInfo = namedtuple("DecInfo", ['type', 'nbits', 'dim', 'vals'])
ShiftInfo = namedtuple("ShiftInfo", ['type', 'count'])
MemAccessPostInfo = namedtuple("MemAccessPostInfo", ['base', 'offsettype', 'offset', 'direction'])
MemAccessPreInfo = namedtuple("MemAccessPretInfo", ['base', 'offsettype', 'offset', 'direction', 'shift'])

tokens = (
   'INSTR',
   'REGISTER',
   'LISTREGS',
   'CONSTANT',
   'COMMENT',
   'INNERSEP',
   'SHIFTREG',
   'SHIFTIMM',
   'SETFLAGS',
   'WRITEBACK',
   'COND',
   'BYTEONLY',
   'UPDATEMODE',
   'LABEL',
   'LABELADDR',
   'MEMACCESSPRE',
   'MEMACCESSPOST',
   'DECLARATION',
   'SECTION'
)

t_ignore_COMMENT = r';.*$'
t_INNERSEP = r','

@lex.TOKEN(regexpInstr)
def t_INSTR(t):
    return t

@lex.TOKEN(r'\[\s*(R[0-9]{1,2}|SP|LR|PC)\s*,\s*(([#](\+|-)?(0x)?[0-9a-fA-F]+)|((\+|-)?R[0-9]{1,2}|SP|LR|PC)(\s*,\s*(LSL|LSR|ASR|ROR)\s+[#][0-9]{1,2})?)\s*]')
def t_MEMACCESSPRE(t):
    rbase = re.search(r'R[0-9]{1,2}|SP|LR|PC', t.value).group(0)
    rbase = int(rbase[1:]) if rbase[0] == "R" else ["SP","LR","PC"].index(rbase)+13

    mode = "reg" if "R" in t.value.split(",")[1] else "imm"
    shift = mode =="reg" and t.value.count(",") > 1
    if not shift:
        other = abs(int(t.value[t.value.index("#")+1:t.value.rindex("]")], 0)) if mode == "imm" else int(t.value[t.value.rindex("R")+1:t.value.rindex("]")])
        shiftInfo = ("LSL", 0)
    else:
        other = int(t.value[t.value[:t.value.rindex(",")].rindex("R")+1:t.value.rindex(",")])
        tmp = re.search(r'(LSL|LSR|ASR|ROR)\s+[#][0-9]{1,2}', t.value).group(0)
        shiftInfo = ShiftInfo(tmp[:3], int(tmp[tmp.index('#')+1:]))
    direction = -1 if "-" in t.value else 1
    t.value = MemAccessPreInfo(rbase, mode, other, direction, shiftInfo)
    return t

@lex.TOKEN(r'\[\s*(R[0-9]{1,2}|SP|LR|PC)\s*](,\s*(([#](\+|-)?(0x)?[0-9a-fA-F]+)|((\+|-)?R[0-9]{1,2}|SP|LR|PC)))?')
def t_MEMACCESSPOST(t):
    rbase = re.search(r'R[0-9]{1,2}|SP|LR|PC', t.value).group(0)
    rbase = int(rbase[1:]) if rbase[0] == "R" else ["SP","LR","PC"].index(rbase)+13

    if t.value[-1] == "]":
        t.value = MemAccessPostInfo(rbase, "imm", 0, 1)
    else:
        mode = "imm" if "#" in t.value else "reg"
        other = abs(int(t.value[t.value.index("#")+1:], 0)) if mode == "imm" else int(t.value[t.value.rindex("R")+1:])
        direction = -1 if "-" in t.value else 1
        t.value = MemAccessPostInfo(rbase, mode, other, direction)
    return t

def t_DECLARATION(t):
    r'D[SC](8|16|32)\s+\w+.*'
    bits = int(t.value.split()[0][2:])
    vals = t.value.split()[1].split(",")
    if len(vals) < 2:
        vals = []
        dim = t.value.split()[1]
    else:
        dim = len(vals)
    dectype = "constant" if t.value[1] == "C" else "variable"
    t.value = namedtuple(dectype, bits, dim, vals)
    return t

def t_SECTION(t):
    r'SECTION\s+(INTVEC|CODE|DATA)'
    t.value = t.value[len('SECTION')+1:].strip()
    return t

def t_REGISTER(t):
    r'(R[0-9]{1})|(R1[0-5]{1})|SP|LR|PC'
    t.value = int(t.value[1:])
    return t

@lex.TOKEN(r'\{[R0-9\-,\s]}')
def t_LISTREGS(t):
    listRegs = [0]*16
    val = t.value.replace(" ", "").replace("\t", "")
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
    for i,(r,end) in enumerate(zip(regs, baseRegsEndPos)):
        if val[end+1] in (',', '}'):
            listRegs[r] = 1
        elif val[end+1] == '-':
            for j in range(r, regs[i+1]):   # Last register not included
                listRegs[j] = 1
    t.value = listRegs
    return t

def t_WRITEBACK(t):
    r'!'
    return t

def t_CONSTANT(t):
    r'[#][+-]?(0x[0-9a-fA-F]+|[0-9]+)'
    t.value = int(t.value[1:], 0)
    return t

def t_SHIFTREG(t):
    r'(LSL|LSR|ASR|ROR)\s+R[0-9]{1,2}'
    t.value = ShiftInfo(t.value[:3], int(t.value[t.value.rindex('R')+1:]))
    return t

def t_SHIFTIMM(t):
    r'(LSL|LSR|ASR|ROR)\s+[#][0-9]{1,2}'
    t.value = ShiftInfo(t.value[:3], int(t.value[t.value.index('#')+1:]))
    return t

def t_COND(t):
    r'(?<=[A-Z])AL|EQ|NE|CS|CC|MI|PL|VS|VC|HS|LO|HI|LS|GE|LT|GT|LE\s+'
    return t

def t_UPDATEMODE(t):
    r'(?<=[A-Z])IA|IB|DA|DB|EA|ED|FA|FD'
    return t

def t_SETFLAGS(t):
    r'(?<=[A-Z])S\s+'
    return t

def t_BYTEONLY(t):
    r'((?<=(LDR|STR))|(?<=((LDR|STR)[A-Z]{2})))B\s+'
    return t

def t_LABELADDR(t):
    r'\s*=\w+'
    t.value = t.value[1:]
    return t

def t_LABEL(t):
    r'\s*\w+'
    t.value = t.value.strip()
    return t

# Define a rule so we can track line numbers
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# A string containing ignored characters (spaces and tabs)
t_ignore  = ' \t'

# Error handling rule
def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)

# Build the lexer
lex.lex(reflags=re.UNICODE)
lexer = lex.lex()