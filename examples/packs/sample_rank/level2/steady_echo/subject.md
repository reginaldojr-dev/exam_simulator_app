Assignment name  : steady_echo
Expected files   : steady_echo.c
Allowed functions: write
--------------------------------------------------------------------------------

Write a program that displays all command-line arguments on a single line,
separated by exactly one space, followed by a newline.

The contents of each argument must be preserved exactly as received.

If no argument is provided, simply display a newline.

The program must terminate normally. A program that exceeds the execution time
limit will be considered a failure.

Examples:

$> ./steady_echo hello world | cat -e
hello world$
$> ./steady_echo "42 Exam" Trainer | cat -e
42 Exam Trainer$
$> ./steady_echo | cat -e
$
$>
