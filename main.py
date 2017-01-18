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
        bytecode, bcinfos, errors = ASMparser(f)

    print(errors)
    exit()

    interpreter = BCInterpreter(bytecode, bcinfos)
    with open(args.inputfile) as f:
        lines = f.readlines()
        a = time.time()
        for i in range(10000):
            print(i, lines[interpreter.getCurrentLine()][:-1])
            interpreter.step()
            print(interpreter.getCurrentLine(), interpreter.getChanges())
            print("################")
    print("Time execute {} instructions : {}".format(i, time.time() - a))





