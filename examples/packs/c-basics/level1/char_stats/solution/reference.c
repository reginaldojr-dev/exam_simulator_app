#include <ctype.h>
#include <stdio.h>
int main(int c,char**v){int a=0,d=0,o=0;if(c>1){for(char*p=v[1];*p;p++){if(isalpha((unsigned char)*p))a++;else if(isdigit((unsigned char)*p))d++;else o++;}}printf("%d %d %d\n",a,d,o);return 0;}
