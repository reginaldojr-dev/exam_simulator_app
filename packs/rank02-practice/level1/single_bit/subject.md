Assignment name  : single_bit
Expected files   : single_bit.c
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

$> ./single_bit alpha beta | cat -e
alpha beta$
$> ./single_bit "42 Exam" Trainer | cat -e
42 Exam Trainer$
$> ./single_bit "" tail | cat -e
 tail$
$> ./single_bit | cat -e
$
$>
