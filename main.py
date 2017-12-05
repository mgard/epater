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
        bytecode, bcinfos, line2addr, assertions, errors = ASMparser(f)
    print("Parsed source code!")
    print(bytecode)


    interpreter = BCInterpreter(bytecode, bcinfos, assertions)
    with open(args.inputfile) as f:
        lines = f.readlines()
        a = time.time()
        for i in range(10):
            if i < 7:
                print(i, lines[interpreter.getCurrentLine()][:-1])
            interpreter.execute(mode='into')
            continue
            b = interpreter.getCurrentLine(), interpreter.getChanges()
            if i < 7:
                print(interpreter.getCurrentLine(), interpreter.getChanges())
                print("################")
        print("...")
    print("Time execute {} instructions : {}".format(i, time.time() - a))





