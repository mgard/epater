import re

from lexparser import lexer, MemAccessPreInfo, ShiftInfo, DummyToken
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
                currentAddr += 4        # Size of an instruction
        maxAddrBySection[currentSection] = currentAddr

        # Third pass : replace all the labels in the instructions
        labelsAddrAddr = {}     # Contains to position of the address of a given label once it have been generated (so we do not generate it again)
        for i,pline in enumerate(parsedCode):
            if len(pline) == 0:
                # We have to keep these empty lines in order to keep track of the line numbers
                continue

            for j,token in enumerate(pline):
                if token.type == "REFLABEL":
                    addrToReach = labelsAddr[token.value]
                    diff = assignedAddr[i] - addrToReach
                    pline[j] = DummyToken("MEMACCESSPRE",
                                          MemAccessPreInfo(15, "imm", abs(diff), diff // abs(diff), ShiftInfo("LSL", 0)))
                elif token.type == "REFLABELADDR":
                    if token.value not in labelsAddrAddr:
                        # We must put the address at the end of the current section
                        # We will have to put these values in memory thereafter
                        labelsAddrAddr[token.value] = maxAddrBySection["CODE"]         # TODO : change section accordingly
                        maxAddrBySection["CODE"] += 4
                    addrToReach = labelsAddrAddr[token.value]
                    diff = assignedAddr[i] - addrToReach
                    pline[j] = DummyToken("MEMACCESSPRE",
                                          MemAccessPreInfo(15, "imm", abs(diff), diff // abs(diff), ShiftInfo("LSL", 0)))

        # Fourth pass : create bytecode
        # At this point, we should have only valid ARM instructions, so let's parse them
        for i,pline in enumerate(parsedCode):
            if len(pline) == 0:
                # We have to keep these empty lines in order to keep track of the line numbers
                continue



        # Fifth pass : add the missing label address


