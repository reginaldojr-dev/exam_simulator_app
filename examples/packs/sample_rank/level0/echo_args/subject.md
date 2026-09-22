Assignment name  : echo_args
Expected files   : echo_args.c
Allowed functions: write
--------------------------------------------------------------------------------

Write a program that displays all command-line arguments on a single line,
separated by exactly one space, followed by a newline.

The contents of each argument must be preserved exactly as received. Do not add
spaces before the first argument or after the last argument.

If no argument is provided, simply display a newline.

Examples:

$> ./echo_args hello world | cat -e
hello world$
$> ./echo_args "42 Exam" Trainer | cat -e
42 Exam Trainer$
$> ./echo_args | cat -e
$
$>
