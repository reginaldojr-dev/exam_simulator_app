#include <stdio.h>

int sum_values(int count, char **values);

int main(int argc, char **argv)
{
    printf("%d\n", sum_values(argc - 1, argv + 1));
    return 0;
}
