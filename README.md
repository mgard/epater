# epater

### An ARM emulator in Python for educational purposes

**epater** (*Environnement de Programmation ARM Téléopéré *) is an ARM emulator targeted for academic and learning purposes. It is a two parts project, consisting of:

1. An assembler program able to translate ARM assembly to ARMv7 bytecode
2. An emulator running ARMv7 bytecode

Unlike many other ARM emulators which *interpret* ARM assembly, **epater** is actually emulating an ARM CPU. This means that one can see (and change) the bytecode in memory and let the emulator run with the modified bytecode.

## Dependencies

* python >= 3.2 (simulator only), >= 3.4 (web interface)
* PLY (Python Lex-Yacc), BSD-licensed. No external dependencies, and might be included at some point in this project.
* python-websockets (web interface only, the simulator itself can run in CLI)


## Currently supported features

* Most ARM7 instructions (data processing, branch, memory operations), including condition codes
* Interrupts (software interrupt using SWI or timer interrupt on either IRQ or FIQ handler)
* Reverse-debugging

## Currently unsupported, but planned features

These features are currently unsupported, but might be included in a future release.

* Multiply long instruction
* Prefetch Abort, Data Abort, and Undefined instruction interrupts
* Real-life PC mode: currently, the user may choose between using a virtualized program counter pointing to the currently executed instruction (that is, as if there was no pipeline) or a PC with a +8 offset to account for the pipeline. In some very specific cases (for instance, when PC is used as an operand, and shifted using another register, or when PC acts as the source register of a STR instruction), the ARM specification reports a PC offset of +12 (see ARM7TDMI reference manual, sec. 4.5.5 and 4.9.4). The simulator currently assumes that the offset is constant, and therefore does not support this mode.
* Hardware interrupts, except for a timer interrupt, e.g. one cannot simulate a keyboard with this emulator
* Load multiple / Store multiple instructions and interrupts: these instructions are special because they may be interrupted in the middle of their execution (whereas all other instructions are atomic regarding the interrupt handling). Currently, LDM and STM are not interrupted.

## Unsupported features

These features are not of great use in a simulation context and/or for academic purposes. Also, a feature may be in this list if the implementation burden would be too high regarding the benefits it might bring. There is currently no plan to implement them, nor to merge a pull request doing that, except some special circumstances.

* Thumb mode
* Jazelle mode
* Accurate processor cycles simulation
* Coprocessor instructions
* Single data swap instructions
* Vectorized / Neon / SIMD instructions
* Privileged mode

More generally, this emulator was not designed with performance in mind, but portability and ease of use.

## License

**epater** is distributed under GPLv3 license.
