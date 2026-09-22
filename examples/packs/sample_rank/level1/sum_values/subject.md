Assignment name  : sum_values
Expected files   : sum_values.c
Allowed functions: none
--------------------------------------------------------------------------------

Write the following function:

int sum_values(int count, char **values);

The function receives an array of numeric strings and returns the sum of the
first count values.

Each string passed by the tester represents a signed base-10 integer. You may
assume the generated values fit inside an int.

If count is 0, the function must return 0.

Examples:

values = {"1", "2", "3"}, count = 3
return value: 6

values = {"-4", "10"}, count = 2
return value: 6

values = {}, count = 0
return value: 0
