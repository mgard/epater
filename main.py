import argparse
import time
import math

from assembler import Assembler
from bytecodeinterpreter import BCInterpreter

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EPATER, ARM emulator')
    parser.add_argument('inputfile', description="Fichier assembleur")
    args = parser.parse_args()

    asm = Assembler()
    with open(args.inputfile) as f:
        asm.parse(f)





