import re

from lexparser import lexer
from instruction import InstructionAsm

class Assembler:
    def __init__(self):
        self.listMnemonics = []

    def parse(self, code):

        for line in code:
            lexer.input(line)
            tokens = []
            while True:
                tok = lexer.token()
                if not tok:
                    break      # End of line
                else:
                    tokens.append(tok)

