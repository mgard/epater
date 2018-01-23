SECTION INTVEC

B main

SECTION CODE

test2
MOV R0, #7
MOV R1, #8
BX LR

main
MOV R0, #4
B test1
MOV R0, #5
test3
MOV R0, #10
B done

test1
MOV R0, #6
BL test2
B test3

done
MOV R5, #1

SECTION DATA
