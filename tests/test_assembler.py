import sys
import pytest
from copy import deepcopy

sys.path.append("..")
from assembler import parse as ASMparser


def bytecodeLoad(line):
    bytecode, bcinfos, _, _ = ASMparser(line)
    return bytecode['SNIPPET_DUMMY_SECTION'], bcinfos

fasm = open('bytecodeTest.asm', 'r')
tlist = []
with open('bytecodeObj.o', 'rb') as fbin:
    fbin.seek(0x34)       # TODO :  compute that automatically

    line = fasm.readline()
    i = 0
    l = 0
    while line != "":
        l += 1
        if len(line.strip()) == 0 or line.strip()[0] == ';':
            line = fasm.readline()
            continue
        bytecode, bcinfos = bytecodeLoad([line])
        if len(bytecode) == 0:
            line = fasm.readline()
            continue
        currentTrueInstr = fbin.read(4)
        tlist.append((currentTrueInstr, bytecode, l, line))

        line = fasm.readline()
        i += 4

@pytest.mark.parametrize("bytecodeIAR,bytecodeEpater,lineno,linetext", tlist)
def test_bytecode(bytecodeIAR, bytecodeEpater, lineno, linetext):
    assert bytecodeIAR == bytecodeEpater, "With {}\nLine / IAR output / epater output : {} / {} / {}".format(linetext, lineno, [hex(int(j)) for j in bytecodeIAR], [hex(int(j)) for j in bytecodeEpater])
