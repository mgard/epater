import re

from instruction import InstructionAsm

class Assembler:
    supportedInst = {'MOV': "Description",
                     'MVN': "Description",
                     'AND': "Description",
                     'ORR': "Description",
                     'EOR': "Description",
                     'BIC': "Description",
                     'ADD': "Description",
                     'SUB': "Description",
                     'MUL': "Description",
                     'DIV': "Description",
                     'ADC': "Description",
                     'SBC': "Description",
                     }
    def __init__(self):
        self.listMnemonics = []

    def parse(self, code):
        mnemonicsRegexp = "|".join(self.listMnemonics)

        reEmpty = re.compile("^\s*$")             # Only spaces
        reCommentOnly = re.compile("^\s*;")       # Comment only (space(s) followed by ;)
        reMnemonic = re.compile("^\s*"+mnemonicsRegexp)       # Zero or more spaces, valid mnemonic
        reLabel = re.compile("^\s*(?!"+mnemonicsRegexp+")\w+\s+")  # Zero or more spaces, one or more characters which are not mnemonic, space(s), something else

        for n,line in enumerate(code):
            if reEmpty.match(line) or reCommentOnly.match(line):
                continue

            if reMnemonic.match(line):
                pass
            elif reLabel.match(line):
                pass
