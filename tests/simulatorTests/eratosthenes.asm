SECTION INTVEC

B main


SECTION CODE

main


LDR R10, =nombres           ; R10 contiendra l'adresse du tableau
; On utilise un tableau de 128 nombres (les chiffres de 0 à 127)
MOV R11, #128               ; R11 contiendra la taille du tableau
ADD R12, R10, R11           ; R12 contiendra l'adresse du premier élément
                            ; après le tableau (autrement dit la fin du tableau)

; 1) Initialisation du tableau de nombres
MOV R0, #0
boucleInit
STRB R0, [R10], #1          ; La valeur de la case mémoire correspond à son décalage par
                            ; rapport au début du tableau
                            ; Nous utilisons des tableaux DS8 (1 octet par élément),
                            ; donc il faut utiliser STRB!
ADD R0, R0, #1              ; On passe à la case suivante
CMP R10, R12
BNE boucleInit              ; Tant que R10 != R12


; 2) Commencer à éliminer les nombres
MOV R5, #2                  ; On commence à 2 (les cas de 0 et 1 sont spéciaux)
bouclePrincipale
LDR R10, =nombres
; On trouve le prochain élément (R5 ou plus) qui n'est pas zéro

boucleRechercheProchainNombrePremier
CMP R5, R11, LSR #1         ; A-t-on atteint la moitié du tableau?
BGE finProgramme            ; Si oui, on a terminé!

LDRB R1, [R10, R5]          ; Si non on lit le nombre à cette adresse
CMP R1, #0                  ; Le nombre à cette adresse est-il 0?
ADDEQ R5, R5, #1            ; Si oui, il faut passer au suivant
                            ; Notez le suffixe EQ : cette addition n'est PAS effectuée
                            ; si R1 n'est pas 0
BEQ boucleRechercheProchainNombrePremier    ; On revient au début de la boucle


; À ce stade-ci, R5 contient le prochain nombre premier dont il faut éliminer les multiples
; On part de ce nombre
ADD R10, R10, R5


; 3) Sauter jusqu'à la fin du tableau 'R5' cases a la fois
MOV R1, #0              ; On ne peut pas directement faire STRB #0, il faut utiliser un registre
boucleMiseAZero
; On doit additionner le nombre avant de faire le STR, ou sinon on va effacer le nombre lui-même!
ADD R10, R10, R5
CMP R10, R12                ; Est-on hors des limites du tableau?
BGE finBoucleMiseAZero      ; Si R10 >= R12, on saute hors de la boucle
STRB R1, [R10]              ; On écrit 0 à cet emplacement
B boucleMiseAZero           ; On passe au nombre suivant dans le tableau

finBoucleMiseAZero
ADD R5, R5, #1              ; On a terminé d'éliminer les multiples de ce nombre premier
                            ; On passe au suivant
B bouclePrincipale


finProgramme
MOV R0, #1

SECTION DATA

nombres DS8 128             ; Tableau contenant les nombres. Sa taille doit correspondre à la
                            ; valeur contenue dans R11 (voir ligne 12)
                            ; Notez que chaque élément fait 1 octet et non 4! (DS8)


