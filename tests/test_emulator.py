
import unicorn
import unicorn.arm_const as ARM

import argparse
import time
import math
import sys
import glob

sys.path.append("..")
from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter
from components import Breakpoint


CODE_START_ADDR = 0x100000
regs_arm = [ARM.UC_ARM_REG_R0, ARM.UC_ARM_REG_R1, ARM.UC_ARM_REG_R2, ARM.UC_ARM_REG_R3,
            ARM.UC_ARM_REG_R4, ARM.UC_ARM_REG_R5, ARM.UC_ARM_REG_R6, ARM.UC_ARM_REG_R7,
            ARM.UC_ARM_REG_R8, ARM.UC_ARM_REG_R9, ARM.UC_ARM_REG_R10, ARM.UC_ARM_REG_R11,
            ARM.UC_ARM_REG_R12, ARM.UC_ARM_REG_R13, ARM.UC_ARM_REG_R14, ARM.UC_ARM_REG_R15]

class Context:
    mode2bits = {'User': 16, 'FIQ': 17, 'IRQ': 18, 'SVC': 19}       # Other modes are not supported
    bits2mode = {v:k for k,v in mode2bits.items()}

    def __init__(self, type_, sim, lengths):
        self.regs = [0 for i in range(16)]
        self.cpsr = 0
        self.spsr = None
        self.mem = None
        self.lengths = lengths
        self.emulator = sim
        self.type = type_

        self.reason = {}

    def __eq__(self, other):
        self.reason = {}
        if self.regs != other.regs:
            self.reason["regs"] = [(i, self.regs[i], other.regs[i]) for i in range(16) if self.regs[i] != other.regs[i]]
        if self.cpsr != other.cpsr:
            self.reason["status"] = ("CPSR", self.cpsr, other.cpsr)
        if self.spsr != other.spsr:
            self.reason["status"] = ("SPSR", self.spsr, other.spsr)
        if self.mem != other.mem:
            self.reason["mem"] = 0

        if len(self.reason) > 0:
            return False
        return True

    def update(self):
        if self.type == "qemu":
            self.from_qemu()
        else:
            self.from_simulator()

    def from_qemu(self):
        self.regs = [self.emulator.reg_read(reg) for reg in regs_arm]
        self.cpsr = self.emulator.reg_read(ARM.UC_ARM_REG_CPSR)
        self.spsr = self.emulator.reg_read(ARM.UC_ARM_REG_SPSR)
        self.mem = {"INTVEC": self.emulator.mem_read(CODE_START_ADDR, self.lengths["INTVEC"]),
                    "CODE": self.emulator.mem_read(CODE_START_ADDR + 0x80, self.lengths["CODE"]),
                    "DATA": self.emulator.mem_read(CODE_START_ADDR + 4096, self.lengths["DATA"])}

    def from_simulator(self):
        self.regsStr = self.emulator.getRegisters()['User']
        self.regs = []
        for i in range(16):
            self.regs.append(self.emulator.sim.regs[i])
        self.regs[15] -= 8
        self.cpsr = self.emulator.sim.regs.CPSR
        self.spsr = 0 # self.sim.sim.regs.getSPSR()
        self.mem = {"INTVEC": self.emulator.sim.mem.data["INTVEC"],
                    "CODE": self.emulator.sim.mem.data["CODE"],
                    "DATA": self.emulator.sim.mem.data["DATA"]}

    def __str__(self):
        s = " " + "_"*96 + " " + "\n"
        if self.type == "qemu":
            s += "|{:^96}|".format("QEMU REFERENCE EMULATOR") + "\n"
        else:
            s += "|{:^96}|".format("EPATER EMULATOR") + "\n"
        s += "|" + "-"*96 + "|" + "\n"
        s += "| " + " |".join(["{:^10}".format("R"+str(i)) for i in range(8)]) + " |" + "\n"
        s += "| " + " |".join(["{:>10}".format(self.regs[i]) for i in range(8)]) + " |" + "\n"
        s += "| " + " |".join(["{:>10}".format(hex(self.regs[i])) for i in range(8)]) + " |" + "\n"
        s += "|" + "-"*96 + "|" + "\n"
        s += "| " + " |".join(["{:^10}".format("R"+str(i)) for i in range(8, 16)]) + " |" + "\n"
        s += "| " + " |".join(["{:>10}".format(self.regs[i]) for i in range(8,16)]) + " |" + "\n"
        s += "| " + " |".join(["{:>10}".format(hex(self.regs[i])) for i in range(8,16)]) + " |" + "\n"
        s += "|" + "-"*96 + "|" + "\n"
        cpsr = "| CPSR : {} (N={}, Z={}, C={}, V={}) / Mode = {}".format(hex(self.cpsr),
                                                                        int(self.cpsr>>31),
                                                                        int(self.cpsr>>30&0x1),
                                                                        int(self.cpsr>>29&0x1),
                                                                        int(self.cpsr>>28&0x1),
                                                                        self.bits2mode[self.cpsr & 0x1F])
        s += "{:<97}".format(cpsr) + "|\n"
        s += "|" + "-"*96 + "|" + "\n"
        return s


def concatenateReports(r1, r2):
    r = ""
    for l1, l2 in zip(r1.split("\n"), r2.split("\n")):
        r += l1 + "   " + l2 + "\n"
    return r

def initializeQemu(machine):
    for reg in regs_arm[:-1]:     # Not the last, because we want to preserve the value of PC!
        machine.reg_write(reg, 0)
    machine.reg_write(ARM.UC_ARM_REG_CPSR, 0x10)        # User-mode



if __name__ == "__main__":
    for inputfile in glob.glob("simulatorTests/*.asm"):

        lines = []
        with open(inputfile) as f:
            bytecode, bcinfos, assertInfos, errors, _ = ASMparser(f, memLayout="test")
        with open(inputfile) as f:
            for line in f:
                lines.append(line)

        # Setting up the QEMU reference ARM simulator
        armRef = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)

        armRef.mem_map(CODE_START_ADDR, 1024*(4 + 2 + 1))       # 4 KB for code, 2 KB for data, 1 KB buffer (just in case)
        contiguousMem = bytearray([0]) * (1024*(4 + 2))
        contiguousMem[0:len(bytecode['INTVEC'])] = bytecode['INTVEC']
        contiguousMem[0x80:0x80+len(bytecode['CODE'])] = bytecode['CODE']
        contiguousMem[4096:4096+len(bytecode['DATA'])] = bytecode['DATA']
        armRef.mem_write(CODE_START_ADDR, bytes(contiguousMem))
        initializeQemu(armRef)

        # Setting up epater simulator
        armEpater = BCInterpreter(bytecode, bcinfos, assertInfos, pcInitAddr=CODE_START_ADDR)
        armEpater.sim.fetchAndDecode()                       # Fetch the first instruction

        memLengths = {"INTVEC": len(bytecode['INTVEC']), "CODE": len(bytecode['CODE']), "DATA": len(bytecode['DATA'])}
        contextRef = Context("qemu", armRef, memLengths)
        contextEpater = Context("epater", armEpater, memLengths)

        cycle = 0
        errorCount = 0
        pcRef = CODE_START_ADDR
        contextRef.update()
        contextEpater.update()
        previousContextRef = str(contextRef)
        previousContextEpater = str(contextEpater)
        tBegin = time.time()
        while cycle < 20000:
            # One step on the reference emulator
            armRef.emu_start(pcRef, CODE_START_ADDR+4096, count=1)
            pcRef = armRef.reg_read(ARM.UC_ARM_REG_R15)

            # One step on epater
            try:
                currentLine = armEpater.getCurrentLine()
            except:
                currentLine = None
            try:
                armEpater.execute("into")
            except Breakpoint as e:
                if e.cmp == "memory" and e.mode == 8:
                    break
                else:
                    raise e

            # Update contexts
            contextRef.update()
            contextEpater.update()

            # print(lines[currentLine].strip())
            if contextRef != contextEpater:
                print("MISMATCH while executing the above instruction!")
                print("\tPrevious CPU context :")
                print(concatenateReports(previousContextRef, previousContextEpater))
                print("\tCPU context after executing {} :".format(lines[currentLine].strip()))
                print(concatenateReports(str(contextRef), str(contextEpater)))
                print("\tDifferences:")
                print(contextRef.reason)
                errorCount += 1
            previousContextRef = str(contextRef)
            previousContextEpater = str(contextEpater)
            cycle += 1

        duration = time.time()-tBegin
        if errorCount:
            print("File {} done in {:.4f} seconds ({:.0f} instr/sec), {} error(s) reported".format(inputfile, duration, cycle/duration, errorCount))
        else:
            print("File {} done in {:.4f} seconds ({:.0f} instr/sec), no errors reported".format(inputfile, duration, cycle/duration))

