Assignment name  : byte_bits
Expected files   : byte_bits.c
Allowed functions: write
--------------------------------------------------------------------------------

Write a program that displays all command-line arguments on a single line,
separated by exactly one space, followed by a newline.

This is an original practice assignment. It is placed at this level to exercise
careful handling of argv, loops, character-by-character output, and edge cases
without relying on an embedded editor or shell-specific behavior.

The contents of each argument must be preserved exactly as received. Do not
trim, transform, reorder, or skip arguments. Do not add a space before the first
argument or after the last argument.

If no argument is provided, simply display a newline.

Examples:

$> ./byte_bits alpha beta | cat -e
alpha beta$
$> ./byte_bits "42 Exam" Trainer | cat -e
42 Exam Trainer$
$> ./byte_bits "" tail | cat -e
 tail$
$> ./byte_bits | cat -e
$
$>
