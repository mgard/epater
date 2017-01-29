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
        bytecode, bcinfos, assertions, errors = ASMparser(f)


    interpreter = BCInterpreter(bytecode, bcinfos, assertions)
    with open(args.inputfile) as f:
        lines = f.readlines()
        a = time.time()
        for i in range(100000):
            #print(i, lines[interpreter.getCurrentLine()][:-1])
            interpreter.step()
            b = interpreter.getCurrentLine(), interpreter.getChanges()
            #print(interpreter.getCurrentLine(), interpreter.getChanges())
            #print("################")
    print("Time execute {} instructions : {}".format(i, time.time() - a))





