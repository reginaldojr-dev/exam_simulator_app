#include "../include/word_score.hpp"
#include <iostream>
int main(int argc,char**argv){ std::string s = argc > 1 ? argv[1] : ""; std::cout << word_score(s) << '\n'; }
