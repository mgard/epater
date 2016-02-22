import argparse
import time
import math

from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EPATER, ARM emulator')
    parser.add_argument('inputfile', help="Fichier assembleur")
    args = parser.parse_args()

    with open(args.inputfile) as f:
        ASMparser(f)





