#include "../include/BoxCounter.hpp"
#include <iostream>
int main(int argc,char**argv){ BoxCounter c; for(int i=1;i<argc;i++) c.add(std::stoi(argv[i])); std::cout << c.total() << '\n'; }
