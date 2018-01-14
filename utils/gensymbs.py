from itertools import product

import instruction

PREFIX = list(instruction.exportInstrInfo.keys())
SUFFIX = [""] + list(instruction.conditionMapping.keys())

PREFIX.extend("".join(x) for x in product(["LDM",], instruction.updateModeLDMMapping.keys()))
PREFIX.extend("".join(x) for x in product(["STM",], instruction.updateModeSTMMapping.keys()))
print(sorted(PREFIX))

PREFIX.extend(["STRB", "LDRB"])
PREFIX.extend([
    'ANDS',
    'EORS',
    'SUBS',
    'RSBS',
    'ADDS',
    'ADCS',
    'SBCS',
    'RSCS',
    'TSTS',
    'TEQS',
    'CMPS',
    'CMNS',
    'ORRS',
    'MOVS',
    'BICS',
    'MVNS',
    'MULS',
    'MLAS',
    'UMULLS',
    'SMULLS',
    'SMLALS',
    'UMLALS',
])


mnemonics = list(product(PREFIX, SUFFIX))
print("|".join(list("".join(x).upper() for x in mnemonics)))
