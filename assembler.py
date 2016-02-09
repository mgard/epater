import re

from lexparser import lexer
from instruction import InstructionToBytecode

class Assembler:
    def __init__(self):
        self.listMnemonics = []

    def parse(self, code):
        # First pass : lexical parsing
        parsedCode = []
        for line in code:
            lexer.input(line)
            parsedCode.append([])
            while True:
                tok = lexer.token()
                if not tok:
                    break      # End of line
                else:
                    parsedCode[-1].append(tok)

        # Second pass : assign memory
        for i,pline in enumerate(parsedCode):
            if len(pline) == 0:
                # We have to keep these empty lines to keep track of the line numbers
                continue
                
        # Third pass : create bytecode


