SECTION INTVEC

etiquette
MOV R1, #0xA
LDR R7, mavariable
B main

mavariable DC32 0x22, 0x1
monautrevariable DC32 0xFFEEDDCC, 0x11223344

SECTION CODE

main
B etiquette
B testmov

testmov
MOV R0, #0
MOV R1, #0xA
MOV R2, #1 LSL R1
MOV R3, #0xF0000000
MOV R4, #0x1000 ASR #3
MOV R5, PC

testop
MOV R0, #4
MOV R1, #0xB
ADD R2, R0, R1
SUB R3, R0, R1
SUB R4, R1, R0
AND R5, R0, R1
ORR R6, R0, R1
XOR R7, R6, R1

testmem
LDR R3, mavariable
LDR R4, =mavariable
LDR R10, [R4, #8]
SUB R6, PC, #8
LDR R7, =variablemem
STR R6, [R7]

testloop
MOV R0, #0
MOV R1, #0xF
loop ADD R0, R0, #1
CMP R0, R1
BNE loop
BEQ skip
MOV R11, #0xEF
skip
MOV R2, #0xFF
MOV R3, #255
SUBS R4, R2, R3
MOVGT R5, #1
MOVLE R5, #2
MOVEQ R6, #3

SECTION DATA

variablemem DS32 10