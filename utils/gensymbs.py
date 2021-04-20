import simulatorOps.utils as utils

"""
Gensymbs is a script used to generate a regular expression to highlight all instructions.
The result should be paste to 'mode-assembly_arm.js'.
"""

def parse(*args):
    if len(args) < 1 or len(args[0]) < 1:
        return []
    index = [len(i) - 1 for i in args]
    indexBak = index[:]
    result = []
    for i in range(1, len(args)):
        tempo = list(args)
        tempo.pop(i)
        result.extend(parse(*tempo))
    while True:
        j = 0
        buff = ""
        for i in index:
            buff += str(args[j][i])
            j += 1
        result.append(buff)
        for i in range(len(index)-1, -1, -1):
            index[i] -= 1
            if index[i] < 0:
                if i == 0:
                    return result
                else:
                    index[i] = indexBak[i]
                    continue
            break

COND = [i for i in utils.conditionMapping]
mnemonics = []

# OP Cond
OP = ['BX', 'B', 'BL', 'CMP', 'CMN', 'TEQ', 'TST', 'MRS', 'MSR', 'SWI', 'CDP', 'MCR', 'MRC', 'PUSH', 'POP', 'NOP']
mnemonics.extend(parse(OP, COND))

# OP Cond S
OP = ['MOV', 'MVN', 'AND', 'EOR', 'SUB', 'RSB', 'ADD', 'ADC', 'SBC', 'RSC', 'ORR', 'BIC', 'MUL', 'MLA', 'UMULL', 'UMLAL', 'SMULL', 'SMLAL', 'LSL', 'LSR', 'ASR', 'ROR', 'RRX']
mnemonics.extend(parse(OP, COND, ['S']))

# OP Cond B T
OP = ['LDR', 'STR']
mnemonics.extend(parse(OP, COND, ['B'], ['T']))

# OP Cond H|SH|SB
OP = ['LDR', 'STR']
mnemonics.extend(parse(OP, COND, ['H', 'SH', 'SB']))

# OP Cond FD|ED|FA|EA|IA|IB|DA|DB
OP = ['LDM', 'STM']
mnemonics.extend(parse(OP, COND, ['FD', 'ED', 'FA', 'EA', 'IA', 'IB', 'DA', 'DB']))

# OP Cond B
OP = ['SWP']
mnemonics.extend(parse(OP, COND, ['B']))

# OP Cond L
OP = ['LDC', 'STC']
mnemonics.extend(parse(OP, COND, ['L']))

# OP
OP = []
mnemonics.extend(parse(OP))

# Remove duplicates
mnemonics = list(set(mnemonics))
print("|".join(list("".join(x).upper() for x in mnemonics)))
