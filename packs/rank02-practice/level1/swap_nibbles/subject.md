Assignment name  : swap_nibbles
Expected files   : swap_nibbles.c
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

$> ./swap_nibbles alpha beta | cat -e
alpha beta$
$> ./swap_nibbles "42 Exam" Trainer | cat -e
42 Exam Trainer$
$> ./swap_nibbles "" tail | cat -e
 tail$
$> ./swap_nibbles | cat -e
$
$>
