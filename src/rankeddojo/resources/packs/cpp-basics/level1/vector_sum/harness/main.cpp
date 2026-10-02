#include "../include/vector_sum.hpp"
#include <iostream>
#include <vector>
int main(int argc,char**argv){ std::vector<int> v; for(int i=1;i<argc;i++) v.push_back(std::stoi(argv[i])); std::cout << sum_values(v) << '\n'; }
