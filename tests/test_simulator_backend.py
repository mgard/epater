import sys
import pytest
from copy import deepcopy

sys.path.append("..")
from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter


def runt(interpreter):
    filedone = False
    errors = []
    interpreter.step(stepMode="run")
    line = 1
    while not filedone:
        try:
            interpreter.step()
        except Exception as e:
            errors.append((line, e))
            filedone = True
        bkpt = interpreter.currentBreakpoint
        if bkpt is None:
            line += 1
            continue
        if bkpt.source == 'memory' and bkpt.mode == 8:
            # We did all the instructions in the file
            filedone = True
        elif bkpt.source == 'assert':
            errors.append((bkpt.infos[0]+2, bkpt.infos[1]))
        line += 1
    if len(errors) > 0:
        assert False, str(errors)

def test_dataop():
    return
    with open("simulatorTests/dataop.asm") as f:
        bytecode, bcinfos, assertInfos, errors = ASMparser(f)

    interpreter = BCInterpreter(bytecode, bcinfos, assertInfos)
    runt(interpreter)


def test_shifts():
    with open("simulatorTests/shifttest1.asm") as f:
        bytecode, bcinfos, assertInfos, errors = ASMparser(f)

    interpreter = BCInterpreter(bytecode, bcinfos, assertInfos)
    runt(interpreter)
