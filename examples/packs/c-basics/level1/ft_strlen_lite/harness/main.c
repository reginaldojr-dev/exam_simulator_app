#include <stddef.h>
#include <stdio.h>
size_t ft_strlen_lite(const char *s);
int main(int argc, char **argv){ const char *s = argc > 1 ? argv[1] : ""; printf("%zu\n", ft_strlen_lite(s)); return 0; }
