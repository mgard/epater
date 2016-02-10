import re

from lexparser import lexer
from instruction import InstructionToBytecode

BASE_ADDR_INTVEC = 0x00
BASE_ADDR_CODE   = 0x80
BASE_ADDR_DATA   = 0x1000

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

        # Second pass : assign memory and define labels
        assignedAddr = [-1]*len(parsedCode)
        currentAddr, currentSection = -1, None
        labelsAddr = {}
        maxAddrBySection = {"INTVEC": BASE_ADDR_INTVEC, "CODE": BASE_ADDR_CODE, "DATA": BASE_ADDR_DATA}
        for i,pline in enumerate(parsedCode):
            if len(pline) == 0:
                # We have to keep these empty lines in order to keep track of the line numbers
                continue
            idxToken = 0

            if pline[0].type == "SECTION":
                if currentSection is not None:
                    maxAddrBySection[currentSection] = currentAddr

                if pline[0].value == "INTVEC":
                    currentSection = "INTVEC"
                    currentAddr = BASE_ADDR_INTVEC
                elif pline[0].value == "CODE":
                    currentSection = "CODE"
                    currentAddr = BASE_ADDR_CODE
                elif pline[0].value == "DATA":
                    currentSection = "DATA"
                    currentAddr = BASE_ADDR_DATA

            if pline[0].type == "LABEL":
                assert currentAddr != -1
                labelsAddr[pline[0].value] = currentAddr
                idxToken += 1

            if pline[idxToken].type == "DECLARATION":
                assert currentAddr != -1
                assignedAddr[i] = currentAddr
                currentAddr += pline[idxToken].value.nbits // 8 * pline[idxToken].value.dim
            elif pline[idxToken].type == "INSTR":
                assert currentAddr != -1
                assignedAddr[i] = currentAddr
                currentAddr += 4

        # Third pass : replace all the labels in the instructions
                
        # Fourth pass : create bytecode


