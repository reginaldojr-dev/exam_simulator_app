#include <stdio.h>
#include <stdlib.h>
int main(int c,char**v){long total=0;for(int i=1;i<c;i++)total+=strtol(v[i],0,10);printf("%ld\n",total);return 0;}
