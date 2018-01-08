
import unicorn
import unicorn.arm_const as ARM

import argparse
import time
import math
import sys

sys.path.append("..")
from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter
from procsimulator import Simulator


CODE_START_ADDR = 0x100000
regs_arm = [ARM.UC_ARM_REG_R0, ARM.UC_ARM_REG_R1, ARM.UC_ARM_REG_R2, ARM.UC_ARM_REG_R3,
            ARM.UC_ARM_REG_R4, ARM.UC_ARM_REG_R5, ARM.UC_ARM_REG_R6, ARM.UC_ARM_REG_R7,
            ARM.UC_ARM_REG_R8, ARM.UC_ARM_REG_R9, ARM.UC_ARM_REG_R10, ARM.UC_ARM_REG_R11,
            ARM.UC_ARM_REG_R12, ARM.UC_ARM_REG_R13, ARM.UC_ARM_REG_R14, ARM.UC_ARM_REG_R15]

class Context:
    def __init__(self):
        self.regs = [0 for i in range(16)]
        self.cpsr = 0
        self.spsr = None
        self.mem = None

        self._reason = {}

    def __eq__(self, other):
        self._reason = {}
        if self.regs != other.regs:
            self._reason["regs"] = [(i, self.regs[i], other.regs[i]) for i in range(16) if self.regs[i] != other.regs[i]]
        if self.cpsr != other.cpsr:
            self._reason["status"] = ("CPSR", self.cpsr, other.cpsr)
        if self.spsr != other.spsr:
            self._reason["status"] = ("SPSR", self.spsr, other.spsr)
        if self.mem != other.mem:
            self._reason["mem"] = 0
            
        if len(self._reason) > 0:
            return False
        return True

    def from_qemu(self, machine):
        self.regs = [machine.reg_read(ARM.UC_ARM_REG_R0 + i) for i in range(16)]
        self.cpsr = machine.reg_read(ARM.UC_ARM_REG_CPSR)
        self.spsr = machine.reg_read(ARM.UC_ARM_REG_SPSR)
        self.mem = machine.mem_read(CODE_START_ADDR, 1024*1024)

    def from_simulator(self, simulator):
        self.regs = simulator.getRegisters()
        self.cpsr = simulator

def initializeQemu(machine):
    for i in range(15):     # Not 16, because we want to preserve the value of PC!
        machine.reg_write(ARM.UC_ARM_REG_R0 + i, 0)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='EPATER simulator test suite')
    parser.add_argument('inputfile', help="Fichier assembleur")
    parser.add_argument('-c', "--count", default=10, type=int, help="Number of steps")
    args = parser.parse_args()

    with open(args.inputfile) as f:
        bytecode, bcinfos, assertInfos, errors, _ = ASMparser(f, memLayout="test")
    
    armRef = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)

    armRef.mem_map(CODE_START_ADDR, 1024*(4 + 2 + 1))       # 4 KB for code, 2 KB for data, 1 KB buffer (just in case)

    contiguousMem = bytearray([0]) * (1024*(4 + 2))
    contiguousMem[0:len(bytecode['CODE'])] = bytecode['CODE']
    contiguousMem[4096:len(bytecode['DATA'])] = bytecode['DATA']
    armRef.mem_write(CODE_START_ADDR, bytes(contiguousMem))

    initializeQemu(armRef)
    cycle = 0
    pc = CODE_START_ADDR
    while cycle < args.count:
        armRef.emu_start(pc, CODE_START_ADDR+4096, count=1)
        pc = armRef.reg_read(ARM.UC_ARM_REG_R15)
        cycle += 1
    
