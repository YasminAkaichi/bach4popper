from parser import Parser
from data_structures import (
    Abs_SITerm,
    SI_ATOMIC, 
    SI_COMPOSED,
    SI_HORN_CLAUSE,
    SI_PRGM,
    SI_THEORIES, 
    AST_PRIMITIVE,
    AST_CLOSE_FUNCTION,
)

def run_test():
    msg = "prgmlen(2) present"
    ast = myparser.parse_comAugStInfo(msg)
    print("Success")

myparser = Parser()
run_test()
