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
        # interpreter.setInterrupt("FIQ", False, 5, 5, 0)
        a = time.time()
        print(interpreter.getChanges())
        print(interpreter.getRegisters())
        print(interpreter.getFlags())
        for i in range(2):
            if i < 37:
                pass
                print(i, lines[interpreter.getCurrentLine()][:-1])
                print(interpreter.getCycleCount())
                print(interpreter.getChanges())
                interpreter.execute(mode='run')

            #print(interpreter.sim.regs[15])

            continue
            b = interpreter.getCurrentLine(), interpreter.getChanges()
            if i < 7:
                print(interpreter.getCurrentLine(), interpreter.getChanges())
                print("################")
        print("...")
        interpreter.stepBack();
        interpreter.stepBack();
        interpreter.stepBack();
        print(interpreter.getChanges())
    print("Time execute {} instructions : {}".format(i, time.time() - a))





