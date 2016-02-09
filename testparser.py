import ply.lex as lex
import re

instructionList = ['MOV', 'LDR', 'STR', 'ADD', 'SUB', 'POP', 'PUSH', 'B']
regexpInstr = (r'|').join(instructionList)

# List of token names.   This is always required
tokens = (
   'INSTR',
   'REGISTER',
   'CONSTANT',
   'COMMENT',
   'INNERSEP',
   'SHIFTREG',
   'SHIFTIMM',
   'SETFLAGS',
   'COND',
   'BYTEONLY',
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

@lex.TOKEN(r'\[\s*(R[0-9]{1,2}|SP|LR|PC)\s*,\s*(([#](\+|-)?(0x)?[0-9a-fA-F]+)|((\+|-)?R[0-9]{1,2}|SP|LR|PC)(\s*,\s*(LSL|LSR|ASR|ROR)\s+[#][0-9]{1,2})?)\s*]!?')
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
        shiftInfo = (tmp[:3], int(tmp[tmp.index('#')+1:]))
    incBeforeAccess = "!" in t.value
    direction = -1 if "-" in t.value else 1
    t.value = (rbase, mode, other, direction, incBeforeAccess, shiftInfo)
    return t

@lex.TOKEN(r'\[\s*(R[0-9]{1,2}|SP|LR|PC)\s*](,\s*(([#](\+|-)?(0x)?[0-9a-fA-F]+)|((\+|-)?R[0-9]{1,2}|SP|LR|PC)))?')
def t_MEMACCESSPOST(t):
    rbase = re.search(r'R[0-9]{1,2}|SP|LR|PC', t.value).group(0)
    rbase = int(rbase[1:]) if rbase[0] == "R" else ["SP","LR","PC"].index(rbase)+13
    
    if t.value[-1] == "]":
        t.value = (rbase, "imm", 0, 1)
    else:
        mode = "imm" if "#" in t.value else "reg"
        other = abs(int(t.value[t.value.index("#")+1:], 0)) if mode == "imm" else int(t.value[t.value.rindex("R")+1:])
        direction = -1 if "-" in t.value else 1
        t.value = (rbase, mode, other, direction)
    return t

def t_DECLARATION(t):
    r'DC(8|16|32)\s+\w+.*'
    dim = int(t.value.split()[0][2:])
    vals = t.value.split()[1].split(",")
    t.value = (dim, vals)
    return t

def t_SECTION(t):
    r'SECTION\s+(INTVEC|CODE|DATA)'
    t.value = t.value[len('SECTION')+1:].strip()
    return t

def t_REGISTER(t):
    r'R[0-9]{1,2}|SP|LR|PC'
    t.value = int(t.value[1:])
    return t

def t_CONSTANT(t):
    r'[#](0x[0-9a-fA-F]+|[0-9]+)'
    t.value = int(t.value[1:], 0)
    return t

def t_SHIFTREG(t):
    r'(LSL|LSR|ASR|ROR)\s+R[0-9]{1,2}'
    t.value = (t.value[:3], int(t.value[t.value.rindex('R')+1:]))
    return t

def t_SHIFTIMM(t):
    r'(LSL|LSR|ASR|ROR)\s+[#][0-9]{1,2}'
    t.value = (t.value[:3], int(t.value[t.value.index('#')+1:]))
    return t

def t_COND(t):
    r'AL|EQ|NE|CS|CC|MI|PL|VS|VC|HS|LO|HI|LS|GE|LT|GT|LE\s+'
    return t

def t_SETFLAGS(t):
    r'(?<=[A-Z])S\s+'
    return t

def t_BYTEONLY(t):
    r'(?<=(LDR|STR))B\s+'
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

data = """
label1
MOV R2, R0 ; ceci est un commentaire
MOV R4, #89 ; ceci MOV R3, #76
; Encore MOV
autrelabel MOVS R3, R1, LSL #5
MOVEQ R0, R1, LSR R5
LDRNE R4, [R3, -R0]
LDR R4, [R3, #12]!
STR R8, [R11], -R4, LSL #2
STR R9, [SP], #+0x22
LDRB R8,[R3]
LDR R3, label2
LDR R7, [R0, R1, ASR #2]
STR R7, =_monadresse
B label1
"""
for i,line in enumerate(data.split("\n")):
    print("Line " + str(i+1))
    lexer.input(line)
    while True:
        tok = lexer.token()
        if not tok: 
            break      # No more input
        print("\t {} -> {}, ligne {}, col {}".format(tok.type, tok.value, tok.lineno, tok.lexpos))

