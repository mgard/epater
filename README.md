# epater

### An ARM emulator in Python for educational purposes

**epater** (*Environnement de Programmation ARM Téléopéré pour l'Éducation et la Recherche*) is an ARM emulator targeted for academic and learning purposes. It is a three parts project, consisting of:

1. An assembler program able to translate ARM assembly to ARMv4 bytecode
2. An emulator running ARMv4 bytecode
3. A web interface to display the emulator state and various debug information

Unlike many other ARM emulators which *interpret* ARM assembly, **epater** is actually emulating an ARM CPU. This means that one can see (and change) the bytecode in memory and let the emulator run with the modified bytecode.

## Dependencies

### Simulator

**epater** may run in CLI mode, in which case it does not need web server components.

* Python >= 3.4
* PLY (Python Lex-Yacc), BSD-licensed. Might be included at some point in this project.

### Web interface

* Python >= 3.5
* greenlet >= 0.4
* gevent >= 1.0
* beautifulsoup >= 4 and bs4
* bottle >= 0.12
* python-websockets >= 3.2

On client side, the following browsers are supported :

* Mozilla Firefox >= 44 on Linux, MacOS or Windows
* Google Chrome >= 50 on Linux, MacOS or Windows
* Microsoft Edge
* Safari

Other configurations may work as well, but have not been tested.

## Currently supported features

* Most ARMv4 instructions (data processing, branch, memory operations), including condition codes (see *Missing instructions* further)
* Interrupts (software interrupt using SWI or timer interrupt on either IRQ or FIQ handler)
* Assertion system, which allows to check for various conditions at runtime
* Comprehensive web interface with a lot of educational features. For instance, the effect of each memory operation can be visualized, as conditionnal branch targets.

## Performances

This emulator was not designed with portability and ease of use in mode rather than performance. While its speed is sufficient for most educational applications, it is not suitable to emulate actual complex ARM programs. Pypy may be used to speed up the simulator and we recommand uvloop for the server side. The server is multi-threaded, but the simulator is not: with *N* cores, *N* simulators may run simultaneously, but one simulator will not benefit from multiple cores. Here are some performance measurements under various conditions:

| Details | Performance (instr/sec) |
| ------- |:-----------------------:|
| Simulator only | 60K |
| Simulator only with pypy | 70K |
| Simulator + web server | 12K |
| Simulator + web server + step by step | 4K | 

*Test configuration* : Core i7 6800K, 64 GB RAM, Python 3.6

## Missing ARMv4 Instructions

These instructions are currently unsupported, but will be added in order to fully support ARMv4 architecture :

* Single data swap (*SWP* and *SWPB*)
* Multiply long instruction (*UMLAL*, *UMULL*, *SMULL*, and *SMLAL*)
* Load and store half-word (*LDRH* and *STRH*)
* Load and store sign extended (*LDRSB*, *STRSB*, *LDRSH*, *STRSH*)
* Load and store with translation (*STRT*, *STRBT*, *LDRT*, and *LDRBT*), although they won't have any special effect in the context of the simulator

All other ARMv4 instructions (mnemonic and bytecode) are supported, except for coprocessor instructions.

## Currently unsupported, but planned features

These features are currently unsupported, but might be included in a future release.

* Prefetch Abort, Data Abort, and Undefined instruction interrupts
* Hardware interrupts, except for a timer interrupt, e.g. one cannot simulate a keyboard with this emulator
* Interrupt integration with load multiple / store multiple instructions: these instructions are special because they may be interrupted in the middle of their execution (whereas all other instructions are atomic regarding the interrupt handling). Currently, LDM and STM are not interrupted.
* Reverse-debugging

## Unsupported features

These features are not of great use in a simulation context and/or for academic purposes. Also, a feature may be in this list if the implementation burden would be too high regarding the benefits it might bring. There is currently no plan to implement them, nor to merge a pull request doing that, except some special circumstances.

* Thumb mode
* Jazelle mode
* Accurate processor cycles simulation
* Coprocessor instructions
* Vectorized / Neon / SIMD instructions
* Privileged mode


## License

**epater** is distributed under GPLv3 license (see LICENSE).
