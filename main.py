import argparse
import time
import math

from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter
from procsimulator import Simulator

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EPATER, ARM emulator')
    parser.add_argument('inputfile', help="Fichier assembleur")
    args = parser.parse_args()

    with open(args.inputfile) as f:
        bytecode, bcinfos = ASMparser(f)

    interpreter = BCInterpreter(bytecode, bcinfos)
    print(interpreter.getCurrentLine(), interpreter.getRegisters())
    interpreter.step()
    print(interpreter.getCurrentLine(), interpreter.getRegisters())
    interpreter.step()
    print(interpreter.getCurrentLine(), interpreter.getRegisters())
    interpreter.step()
    print(interpreter.getCurrentLine(), interpreter.getRegisters())
    interpreter.step()
    print(interpreter.getCurrentLine(), interpreter.getRegisters())






