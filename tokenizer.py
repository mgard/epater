import re
from collections import namedtuple
import ply.lex as lex

import instruction as instrInfos


tokens = (
   'COMMENT',
   'SPACEORTAB',
   'ENDLINESPACES',
   'SPACES',
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
   'MODIFYFLAGS',
   'LDMMODE',
   'STMMODE',
   'REG',
   'CONST',
   'INNERSHIFT',
   'OPDATA2OP',
   'OPDATA3OP',
   'OPDATATEST',
   'OPMEM',
   'OPMULTIPLEMEM',
   'OPSHIFT',
   'OPBRANCH',
   'LABEL',
)

t_COMMENT = r'\s+;.*$'
t_COMMA = r',[\t ]*'
t_SPACEORTAB = r'[ \t]'
t_ENDLINESPACES = r'(?<=\S)\s*$'
t_ignore_SPACES = r'\s'
t_SHARP = r'\#'
t_OPENBRACKET = r'\['
t_CLOSEBRACKET = r'\]'
t_OPENBRACE = r'{'
t_CLOSEBRACE = r'}'
t_CARET = r'\^'
t_EXCLAMATION = r'!'

@lex.TOKEN(r'(' + "|".join(instrInfos.conditionMapping.keys())+')')
def t_CONDITION(t):
    return t

def t_MODIFYFLAGS(t):
    r'S'
    return t

def t_BYTEONLY(t):
    r'B'
    return t

@lex.TOKEN(r'(' + "|".join(instrInfos.updateModeLDMMapping.keys())+')')
def t_LDMMODE(t):
    return t

@lex.TOKEN(r'(' + "|".join(instrInfos.updateModeSTMMapping.keys())+')')
def t_STMMODE(t):
    return t

def t_REG(t):
    r'(R0|R1|R2|R3|R4|R5|R6|R7|R8|R9|R10|R11|R12|R13|R14|R15|SP|LR|PC)'
    return t

def t_CONST(t):
    r'[+-]?(0x[0-9a-fA-F]+|[0-9]+)'
    t.value = int(t.value.strip(), 16) if '0x' in t.value.lower() else int(t.value.strip())
    return t

def t_INNERSHIFT(t):
    r'(LSL|LSR|ASR|ROR|RRX)'
    return t

def t_OPDATA2OP(t):
    r'(MOV|MVN)'
    return t

def t_OPDATA3OP(t):
    r'(AND|EOR|SUB|RSB|ADD|ADC|SBC|RSC|ORR|BIC)'
    return t

def t_OPDATATEST(t):
    r'(CMP|CMN|TST|TEQ)'
    return t

@lex.TOKEN(r'(' + "|".join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.memop])+')')
def t_OPMEM(t):
    return t

@lex.TOKEN(r'(' + "|".join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.shiftop])+')')
def t_OPSHIFT(t):
    return t

@lex.TOKEN(r'(' + "|".join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.multiplememop])+')')
def t_OPMULTIPLEMEM(t):
    return t

@lex.TOKEN(r'(' + "|".join([k for k,v in instrInfos.exportInstrInfo.items() if v == instrInfos.InstrType.branch])+')')
def t_OPBRANCH(t):
    return t

def t_LABEL(t):
    r'\w+(\s+|\Z)'
    return t

# Error handling rule
def t_error(t):
    print("Caractere invalide (ligne {}, colonne {}) : {}".format(t.lineno, t.lexpos, t.value[0]))
    #print("Illegal character '%s'" % t.value[0])
    #t.lexer.skip(1)

lex.lex()