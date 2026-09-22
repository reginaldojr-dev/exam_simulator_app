#include <stdio.h>

int main(int argc, char **argv)
{
    int i;

    i = 1;
    while (i < argc)
    {
        if (i > 1)
            printf(" ");
        printf("%s", argv[i]);
        i++;
    }
    printf("\n");
    return (0);
}
