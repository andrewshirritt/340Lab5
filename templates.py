"""
Templates used by the nimble2arm.py module

Authors: TODO: your names here

Date: TODO: submission date here
"""

script = """\
.syntax unified
.include "syscall.inc"
    
.section .rodata

true_string: .asciz "true"
false_string: .asciz "false"
    
{string_literals}

.section .text

/* subroutine to count length of strings*/
string_length:
mov r2, #0

loop_start:
ldr r1, [r0],1
add r2, r2, #1
cbz r1, loop_end
b loop_start

loop_end:
mov r0,r2
bx lr


/* subroutine to copy string from r0 into space of r1, stops when encounters /0 */
string_copy:

copy_start:
ldr r2, [r0],1
cbz r2, copy_end
str r2, [r1]
b copy_start

copy_end:
bx lr


true_false_string:
cbz r0, choose_false
ldr r1, =true_string
b end_true_false_string
choose_false:
ldr r1, =false_string
end_true_false_string:
bx lr

.global main
.thumb_func
main:

{main}

halt:

bkpt #1      // Break at end of main
bx lr        // Implicit return
"""

add_sub = """\
{expr0}
str r0, [sp, #-4]! 
{expr1}
ldr r1, [sp], #4 
{operation} r0, r1, r0
"""

cat = """\
/* concatenating two strings */

{expr0} /* pointer to string 0 label*/
str r0, [sp, #-4]! /* puts address zero on the stack*/
bl string_length /* finds length puts it in r0 */
str r0, [sp, #-4]! /* puts length of zero on the stack */
  
{expr1} /* pointer to string 1 label*/
str r0, [sp, #-4]! /* puts address one on the stack*/
bl string_length /* finds length puts it in r0 */
str r0, [sp, #-4]! /* puts length of string one on the stack */

add r1,r0,r1    /* adds lengths together */ 
add r1,r1, #1   /* accounts for null terminator */ 
mov r0, #2 
syscall      /* syscall with r0 = 2 mallocs number of bytes in r1, returns heap address in r0*/
str r0, [sp, #-4]!      /* puts heap address on the stack*/

/*copy both strings into one*/
ldr r0,[sp, #-16]
ldr r1,[sp]
bl string_copy
ldr r0,[sp, #-8]
ldr r1,[sp]
bl string_copy
ldr r0,[sp]
sub sp, sp, #16

"""

if_ = """\
{condition}
cbz r0, {endif_label}
{true_block}
{endif_label}:
"""

if_else = """\
{condition}
cbz, r0 {false_label}
{true_block}
b {end_label}
{false_label}
{false_block}
b {end_label}
{end_label}
"""


print_int_or_string = """\
{expr}
mov r1, r0
mov r0, {service_code}
syscall
"""

# for printing booleans, we want to print true/false rather than 1/0
# so we start by loading the corresponding string address in to r1
# using the true_false_string subroutine
#
# alternate approach: embed the true_false_subroutine code directly
# in the `print_bool` template, removing the `bl` instruction at the
# end and with unique, dynamically generated `choose_false` and
# `end_true_false_string` labels

print_bool = """\
{expr}
bl true_false_string
mov r0, #0
syscall
"""
