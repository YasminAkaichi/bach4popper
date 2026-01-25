"""

 Copyright (c) 2025 Jean-Marie Jacquet and Manel Barkallah
 
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


from data_structures import (
    Abs_SITerm,
    SI_ATOMIC,
    SI_COMPOSED,
    SI_HORN_CLAUSE,
    SI_PRGM,
    SI_THEORIES, 
    Abs_AG,
    AST_PRIMITIVE,
    Abs_Aux_Fct,
    AST_CLOSE_FUNCTION,
)

from store import STORE

class Interpreter:
    def __init__(self, store):
        self.theStore = store

    def eval(self,ast,pid):
        if isinstance(ast, Abs_AG):
            return self.eval_primitive(ast,pid)
        elif isinstance(ast, Abs_Aux_Fct):
            return self.eval_aux_fct(ast,pid)
        else:
            print("Not yet treated")
            return (False,"Statement not yet treated")

        
    def eval_primitive(self,ast,pid):
        prim = ast.primitive
        functor = ast.argument.functor
        sarg = str(ast.argument)
        if prim == "tell":
            print(f"functor = {functor}")
            rsarg = sarg
            print(f"rsarg = {rsarg}")
            return self.theStore.tell(functor,rsarg,pid)
        elif prim == "ask":
            print(f"functor = {functor}")
            rsarg = sarg
            print(f"rsarg = {rsarg}")
            return self.theStore.ask(functor,rsarg,pid)
        elif prim == "reset":
            return self.theStore.reset_store(pid)
        elif prim == "get":
            print(f"functor = {functor}")
            rsarg = sarg
            print(f"rsarg = {rsarg}")
            return self.theStore.get(functor,rsarg,pid)
        elif prim == "nask":
            print(f"functor = {functor}")
            rsarg = sarg
            print(f"rsarg = {rsarg}")
            return self.theStore.nask(functor,rsarg,pid)
        elif prim == "inbb":
            print(f"functor = {functor}")
            rsarg = sarg
            print(f"rsarg = {rsarg}")
            return self.theStore.inbb(functor,rsarg,pid)
        elif prim == "tellprgm":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "prgm(" + sarg + ")"
            return self.theStore.tell(functor,rsarg,pid)
        elif prim == "askprgm":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "prgm"
            return self.theStore.ask(functor,rsarg,pid)
        elif prim == "getprgm":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "prgm(" + sarg + ")"
            return self.theStore.get(functor,rsarg,pid)
        elif prim == "naskprgm":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "prgm"
            return self.theStore.nask(functor,rsarg,pid)
        elif prim == "inprgm":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "prgm"
            return self.theStore.inbb(functor,rsarg,pid)
        elif prim == "tellth":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "th(" + sarg + ")"
            return self.theStore.tell(functor,rsarg,pid)
        elif prim == "askth":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "th"
            return self.theStore.ask(functor,rsarg,pid)
        elif prim == "getth":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "th(" + sarg + ")"
            return self.theStore.get(functor,rsarg,pid)
        elif prim == "naskth":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "th"
            return self.theStore.nask(functor,rsarg,pid)
        elif prim == "inth":
            print(f"functor = {functor}")
            print(f"sarg = {sarg}")
            rsarg = "th"
            return self.theStore.inbb(functor,rsarg,pid)
        else:
            print("error in evaluating primitive")
            return (False, "Error in evaluating a primitive") 

    def eval_aux_fct(self,ast,pid):
        pid.send("closed".encode("utf-8"))
        return (True,"close")
        
