#include <stdio.h>
#include <stdlib.h>
int main(int c,char**v){if(c<3){printf("\n");return 0;}int n=atoi(v[1]);for(int i=0;i<n;i++){if(i)printf(" ");printf("%s",v[2]);}printf("\n");return 0;}
