Assignment name  : sum_even_range
Expected files   : sum_even_range.c
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

$> ./sum_even_range alpha beta | cat -e
alpha beta$
$> ./sum_even_range "42 Exam" Trainer | cat -e
42 Exam Trainer$
$> ./sum_even_range "" tail | cat -e
 tail$
$> ./sum_even_range | cat -e
$
$>
