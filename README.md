# epater

### An ARM emulator in Python for educational purposes with a web GUI

![Example screenshot](/doc/sample_screenshot3.png "")

**epater** (*Environnement de Programmation ARM Téléopéré pour l'Éducation et la Recherche*) is an ARM assembler and emulator targeted for academic and learning purposes. It is composed of three independent parts:

1. An assembler translating ARM assembly to ARMv4 bytecode
2. An emulator running ARMv4 bytecode
3. A web interface to display the emulator state along with various debug information and allow the user to easily interact with the emulator

Unlike many other ARM emulators which *interpret* ARM assembly, **epater** is actually emulating an ARM CPU. This means that one can observe the bytecode in memory, change it on the fly and let the emulator run with the modified bytecode.

## Usage

First ensure that you have installed all the required dependencies (see below) and clone the repository. Then, generate the i18n resource files:

    python utils/po2mo.py

Thereafter, launch a local version of the system using this command:

    python mainweb.py DEBUG

The system will then be available at http://127.0.0.1:8000/.

## Dependencies

### Simulator

**epater** may run in CLI mode (use main.py instead of mainweb.py), in which case it does not need web server components.

* Python >= 3.4
* PLY (Python Lex-Yacc), BSD-licensed. Might be included at some point in this project.

### Web interface

* Python >= 3.5
* greenlet >= 0.4
* gevent >= 1.0
* beautifulsoup >= 4 and bs4
* bottle >= 0.12
* bottle_i18n
* python-websockets >= 3.2
* uvloop (optional)
* polib (optional)

On client side, the following browsers are supported :

* Mozilla Firefox >= 44 on Linux, MacOS or Windows
* Google Chrome >= 50 on Linux, MacOS or Windows
* Microsoft Edge
* Safari

Other configurations may work as well, but have not been tested.

## Currently supported features

* All ARMv4 instructions, except for coprocessor instructions
* Interrupts (software interrupt using SWI or timer interrupt on either IRQ or FIQ handler)
* Assertion system, which allows to check for various conditions at runtime
* Comprehensive web interface with a lot of educational features. For instance, the effect of each memory operation can be visualized, as conditionnal branch targets
* Integrated debugger, including reverse-debugging
* I18n support (currently, most of the UI is in French, but we are gradually improving English translations)

## Performances

**epater** was primarily designed with portability and ease of use in mind. While its speed is more than sufficient for most educational applications, it is not suitable for complex ARM programs emulation. Pypy may be used to speed up the simulator and we recommand uvloop for the server side. The simulator is not multi-threaded. Here are some performance measurements under various conditions:

| Details | Performance (instr/sec) |
| ------- |:-----------------------:|
| Simulator only | 50K |
| Simulator only with pypy | 140K |
| Simulator + web server | 48K |
| Simulator + web server + step by step | 5K | 

*Test configuration* : Core i7 6800K, 64 GB RAM, Python 3.6 (using uvloop for the web server) / Pypy3 5.10

## Currently unsupported, but planned features

These features are currently unsupported, but might be included in a future release.

* Prefetch Abort, Data Abort, and Undefined instruction exceptions and CPU modes
* Hardware interrupts, except for a timer interrupt, e.g. one cannot simulate a keyboard with this emulator
* Interrupt integration with load multiple / store multiple instructions: these instructions are special because they may be interrupted in the middle of their execution (whereas all other instructions are atomic regarding the interrupt handling). Currently, LDM and STM are not interrupted.

## Unsupported features

These features are not of great use in a simulation context and/or for academic purposes. Also, a feature may be in this list if the implementation burden is too high compared to its benefits. There is currently no plan to implement them, nor to merge a pull request doing so, except some special circumstances.

* Thumb mode
* Jazelle mode
* Accurate processor cycles simulation
* Coprocessor instructions
* Vectorized / Neon / SIMD instructions
* Privileged mode (STRT and LDRT are supported, but behave exactly the same as LDR and STR)

## License

**epater** is distributed under GPLv3 license (see LICENSE).
