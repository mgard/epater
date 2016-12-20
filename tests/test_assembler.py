import sys
import pytest

sys.path.append("..")
from assembler import parse as ASMparser

def bytecodeLoad():
    with open('bytecodeTest.asm', 'r') as f:
        bytecode, bcinfos = ASMparser(f)
    return bytecode, bcinfos

def test_bytecode():
    bytecode, bcinfos = bytecodeLoad()
    bytecode = bytecode['SNIPPET_DUMMY_SECTION']
    with open('bytecodeObj.o', 'rb') as f:
        f.seek(0x34)       # TODO :  compute that automatically
        for i in range(0, len(bytecode), 4):
            currentTrueInstr = f.read(4)
            assert currentTrueInstr == bytecode[i:i+4], "Line / IAR output / epater output : {} / {} / {}".format(bcinfos[i][-1]+1, [hex(int(j)) for j in currentTrueInstr], [hex(int(j)) for j in bytecode[i:i+4]])
