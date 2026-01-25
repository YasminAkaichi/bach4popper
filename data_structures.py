"""

 Copyright (c) 2025 Jean-Marie Jacquet
 
 Permission is hereby granted, free of charge, to any person obtaining
 a  copy of  this  software and  associated  documentation files  (the
 "Software"), to  deal in the Software  without restriction, including
 without limitation the  rights to use, copy,  modify, merge, publish,
 distribute, sublicense,  and/or sell copies  of the Software,  and to
 permit persons to whom the Software is furnished to do so, subject to
 the following conditions:
 
 The  above  copyright notice  and  this  permission notice  shall  be
 included in all copies or substantial portions of the Software.
 
 THE  SOFTWARE IS  PROVIDED "AS  IS",  WITHOUT WARRANTY  OF ANY  KIND,
 EXPRESS OR  IMPLIED, INCLUDING BUT  NOT LIMITED TO THE  WARRANTIES OF
 MERCHANTABILITY,    FITNESS   FOR    A    PARTICULAR   PURPOSE    AND
 NONINFRINGEMENT. IN NO  EVENT SHALL THE AUTHORS  OR COPYRIGHT HOLDERS
 BE LIABLE  FOR ANY CLAIM, DAMAGES  OR OTHER LIABILITY, WHETHER  IN AN
 ACTION OF  CONTRACT, TORT OR  OTHERWISE, ARISING  FROM, OUT OF  OR IN
 CONNECTION WITH  THE SOFTWARE  OR THE  USE OR  OTHER DEALINGS  IN THE
 SOFTWARE.

"""


from abc import ABC, abstractmethod


# ------------------------------------------------------------------- #
#                                                                     #
#                              SI-terms                               #
#                                                                     #
#      structured information terms which serve as arguments of       #
#           BLPy primitives : tell, ask, nask, get, in                #
#                                                                     #
#                                                                     #
#     rem: modify from version 1 to treat atomic si-terms as          #
#          composed si-terms                                          #
#                                                                     #
# ------------------------------------------------------------------- #

class Abs_SITerm(ABC):
    def __hash__(self):
        return hash(str(self))
    def __eq__(self,other):
        return str(self) == str(other)

class SI_ATOMIC(Abs_SITerm):
    def __init__(self, functor: str):
        self.functor = functor
    def __repr__(self): return '%s' % (self.functor)
    def __str__(self): return '%s' % (self.functor)
    def convert_to_si_composed(self):
        return SI_COMPOSED(self.functor,[])
    @property
    def name(self): return '%s' % (self.functor)
    @property
    def arity(self): return 0
    @property
    def isAtomic(self): return True
    @property
    def isComposed(self): return False
        
class SI_COMPOSED(Abs_SITerm):
    def __init__(self, functor: str, arguments: list):
        self.functor = functor
        self.arguments = arguments
    def __repr__(self):
        return '%s(%s)' % (self.functor, ', '.join([repr(arg) for arg in self.arguments]))
    def __str__(self):
        return '%s(%s)' % (self.functor, ', '.join([str(arg) for arg in self.arguments]))
    def convert_to_si_composed(self):
        return SI_COMPOSED(self.functor,self.arguments)
    @property
    def name(self): return '%s' % (self.functor)
    @property
    def arity(self): return len(self.arguments)
    @property
    def isAtomic(self): return False
    @property
    def isComposed(self): return True

class SI_HORN_CLAUSE(Abs_SITerm):
    def __init__(self, head: Abs_SITerm, body: list):
        self.head = head
        self.body = body
    def __repr__(self):
        return '%s :- %s.' % (repr(self.head), ', '.join([repr(arg) for arg in self.body]))
    def __str__(self):
        return '%s :- %s.' % (str(self.head), ', '.join([str(arg) for arg in self.body]))
    @property
    def name(self): return '%s' % (repr(self.head))
    @property
    def arity(self): return len(self.arguments)
    @property
    def isAtomic(self): return False
    @property
    def isComposed(self): return True

class SI_PRGM(Abs_SITerm):
    def __init__(self, arguments: list):
        self.functor = "prgm"
        self.arguments = arguments
    def __repr__(self):
        return '{ %s }' % ( ', '.join([repr(arg) for arg in self.arguments]) )
    def __str__(self):
        str_lhc = ', '. join([str(hc) for hc in self.arguments])
        return '{ %s }' % (str_lhc)
    def convert_to_si_composed(self):
        return SI_COMPOSED("prgm",self.arguments)
    @property
    def name(self): return '%s' % (self.functor)
    @property
    def arity(self): return len(self.arguments)
    @property
    def isAtomic(self): return False
    @property
    def isComposed(self): return True
    
class SI_THEORIES(Abs_SITerm):
    def __init__(self, arguments: list):
        self.functor = "theories"
        self.arguments = arguments
    def __repr__(self):
        return '{ %s }' % ( ', '.join([repr(arg) for arg in self.arguments]) )
    def __str__(self):
        str_lth = ', '. join([str(th) for th in self.arguments])
        return '{ %s }' % (str_lth)
    def convert_to_si_composed(self):
        return SI_COMPOSED("theories",self.arguments)
    @property
    def name(self): return '%s' % (self.functor)
    @property
    def arity(self): return len(self.arguments)
    @property
    def isAtomic(self): return False
    @property
    def isComposed(self): return True
    

    
# ------------------------------------------------------------------- #
#                                                                     #
#                            BLPy agents                              #
#                                                                     #
#               BLPy agents limited here to primitives                #
#                                                                     #
# ------------------------------------------------------------------- #

class Abs_AG(ABC):
    pass

class AST_PRIMITIVE(Abs_AG):
    def __init__(self, primitive:str, argument:Abs_SITerm):
        self.primitive = primitive
        self.argument = argument
    def __repr__(self): return '%s(%s)' % (self.primitive, repr(self.argument))
    def __str__(self): return '%s(%s)' % (self.primitive, str(self.argument))    


# ------------------------------------------------------------------- #
#                                                                     #
#                        Auxiliary functions                          #
#                                                                     #
#    copied from work on Bach                                         #
#    essentially close instruction                                    #
#                                                                     #
# ------------------------------------------------------------------- #

class Abs_Aux_Fct(ABC):
    pass

class AST_CLOSE_FUNCTION(Abs_Aux_Fct):
    def __init__(self, primitive:str, largs:list):
        self.primitive = primitive
        self.largs = largs
    def __repr__(self): return '%s' % (self.primitive)
    def __str__(self): return '%s' % (self.primitive)    

    
    

        
