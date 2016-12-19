import sys
import pytest

sys.path.append("..")
from assembler import parse as ASMparser

def bytecodeLoad():
    with open('bytecodeTest.asm', 'r') as f:
        bytecode, bcinfos = ASMparser(f)
    return bytecode

def test_bytecode():
    bytecode = bytecodeLoad()
    with open('bytecodeObj.o', 'rb') as f:
        f.seek(0x30D)       # TODO :  compute that automatically
        for i in range(0, len(bytecode), 4):
            currentTrueInstr = f.read(4)
            assert currentTrueInstr == bytecode[i:i+4]
