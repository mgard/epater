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
        bytecode, bcinfos, line2addr, assertions, _, errors = ASMparser(f)
    print("Parsed source code!")

    a = time.time()
    interpreter = BCInterpreter(bytecode, bcinfos, assertions)
    with open(args.inputfile) as f:
        lines = f.readlines()
        interpreter.step(stepMode="forward")
        print("Cycle {}".format(interpreter.getCycleCount()))
        print("Next line to execute : " + lines[interpreter.getCurrentLine()][:-1])
        interpreter.step(stepMode="into")
        print("Cycle {}".format(interpreter.getCycleCount()))
        print("Next line to execute : " + lines[interpreter.getCurrentLine()][:-1])
        interpreter.execute(mode="run")
        print("Cycle {}".format(interpreter.getCycleCount()))
        print("Final registers values:")
        print(interpreter.getRegisters())
    
    deltaTime = time.time() - a
    cycles = interpreter.getCycleCount()
    cyclesPerSec = cycles / deltaTime
    print("Time execute {} instructions : {} ({:.0f} instr/sec)".format(cycles, deltaTime, cyclesPerSec))
