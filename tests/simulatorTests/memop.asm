SECTION INTVEC

B main

variable1 ASSIGN32 0x04, -1, 42, 0xFFFFFE, 14, 1, 0x800000, -42, 0xFF, 0xF00
variable2 ASSIGN16 2, -1, 0x7FFF, 0x42
variable3 ASSIGN8 1, -2, 4, -8, 16, -32, 64, 128

str1 ASSIGN8 "This is a string"
str2 ASSIGN8 "This is a null-terminated string", 0

SECTION CODE

main
; Load pointers
LDR R0, =variable1
LDR R1, =variable2
LDR R2, =memvar1
LDR R3, =0x3003211F

MOV R3, #4
MOV R4, #2
MOV R5, #1

; Load ops (32 bits)
LDR R8, [R0, #4]
LDR R8, [R0, R3]
LDR R8, [R0, R5, LSL #2]!
LDR R8, [R0], #4
LDR R8, [R0], R4, LSL #1
LDR R8, [R0, -R3]

; Load ops (16 bits, signed and unsigned)
LDRH R9, [R1]
LDRSH R9, [R1]
LDRH R9, [R1, #2]
LDRSH R9, [R1, R4]!
LDRH R9, [R1], #2
LDRH R9, [R1]
LDRSH R9, [R1, -R4]

; Load ops (8 bits, signed and unsigned)
LDR R10, =variable3
LDRB R11, [R10]
LDRB R11, [R10, #1]
LDRB R11, [R10, R4]!
LDRB R11, [R10, #1]
LDRSB R11, [R10, #1]
LDRSB R11, [R10, #2]

; Store ops
LDR R0, =memvar1
LDR R1, =memvar2
LDR R2, =memvar4
MOV R6, #0xA5
MOV R7, #0x7F000000

STR R6, [R0]
STR R6, [R0], #4
STR R6, [R0], R3
STR PC, [R0]
STR R7, [R0, R4, LSL #1]
STR R7, [R0, R4, LSL #1]!
STRH R6, [R1]
STRH R7, [R1], #2
STRB R6, [R1]
STRB R7, [R2, #3]!
STRB R7, [R2, #5]!
STRB R7, [R2], #1

; Store multiple
LDR R0, =memvar3
STMIB R0, {R4,R8-R11}
STMIA R0, {R4,R8-R11}
STMDB R0, {R4,R8-R11}
STMDA R0, {R4,R8-R11}
STMFA R0, {R4,R8-R11}
STMEA R0, {R4,R8-R11}
STMFD R0, {R4,R8-R11}
STMED R0, {R4,R8-R11}
STMIB R0!, {R4,R8-R11}
STMIA R0!, {R4,R8-R11}
STMDB R0!, {R4,R8-R11}
STMDA R0!, {R4,R8-R11}
STMFA R0!, {R4,R8-R11}
STMEA R0!, {R4,R8-R11}
STMFD R0!, {R4,R8-R11}
STMED R0!, {R4,R8-R11}
LDR SP, =memvar3
PUSH {R4,R8-R11}

; Load multiple
LDR R0, =memvar3
LDMIB R0, {R4,R8-R11}
LDMIA R0, {R4,R8-R11}
LDMDB R0, {R4,R8-R11}
LDMDA R0, {R4,R8-R11}
LDMFA R0, {R4,R8-R11}
LDMEA R0, {R4,R8-R11}
LDMFD R0, {R4,R8-R11}
LDMED R0, {R4,R8-R11}
LDMIB R0!, {R4,R8-R11}
LDMIA R0!, {R4,R8-R11}
LDMDB R0!, {R4,R8-R11}
LDMDA R0!, {R4,R8-R11}
LDMFA R0!, {R4,R8-R11}
LDMEA R0!, {R4,R8-R11}
LDMFD R0!, {R4,R8-R11}
LDMED R0!, {R4,R8-R11}
LDR SP, =memvar3
POP {R4,R8-R11}

; LDM/STM with PC
LDR SP, =memvar3
ADD SP, SP, #4
ADD R1, PC, #8
PUSH {R1}
POP {PC}
MOV R0, #145
MOV R0, #211

; Swap operations
LDR R0, =variable1
LDR R1, =variable2
LDR R2, =str1
SWP R5, R4, [R0]
SWPB R5, R4, [R2]



SECTION DATA

memvar1 ALLOC32 40
memvar2 ALLOC16 10
memvar3 ALLOC32 1
memvar4 ALLOC8 100
