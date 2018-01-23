import sys
import pytest
from copy import deepcopy
import subprocess

sys.path.append("..")
from assembler import parse as ASMparser


def bytecodeLoad(line):
    bytecode, bcinfos, _, _, _, _ = ASMparser(line)
    return bytecode['SNIPPET_DUMMY_SECTION'], bcinfos

fasm = open('bytecodeTest.asm', 'r')
print("Assembling test file using arm-none-eabi target")
p1 = subprocess.run(["arm-none-eabi-as", "-march=armv4t", "bytecodeTest.asm", "-o", "asmTest.elf"])
p2 = subprocess.run(["arm-none-eabi-objcopy", "-O", "binary", "asmTest.elf", "asmTest.bin"])
p1.check_returncode()
p2.check_returncode()

tlist = []
with open('asmTest.bin', 'rb') as fbin:
    fbin.seek(0x00)

    line = fasm.readline()
    i = 0
    l = 0
    while line != "":
        l += 1
        if len(line.strip()) == 0 or line.strip()[0] == '@':
            line = fasm.readline()
            continue
        # GCC uses a specific assembly format, where comments are
        # prefixe by a @ (instead of ;) and labels must finish with colon
        # We remove this since our simulator do not support them
        #
        line = line.replace("@", ";").replace(":", "").strip()

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
