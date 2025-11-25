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



# ------------------------------------------------------------------ #
#                                                                    #
#                               STORE                                #
#                                                                    #
#  Version 1                                                         #
#                                                                    #
#       A store is represented as a dictionary mapping the           #
#       string representation of a si-term to an integer             #
#       counting the number of occurrences of this si-term           #
#                                                                    #
#  Version 2                                                         #
#                                                                    #
#       To allow for partially specified si-terms in ask             #
#       primitives, a store is represented as a dictionary           #
#       mapping the string representation of a si-term functor       #
#       to a dictionary mapping the string representation of         #
#       the whole si-term to an integer counting the number of       #
#       occurrences of this si-term                                  #
#                                                                    #
# ------------------------------------------------------------------ #

import threading

from data_structures import SI_ATOMIC, SI_COMPOSED, SI_HORN_CLAUSE, SI_PRGM, SI_THEORIES
from parser import Parser


class STORE:

    def __init__(self):
        self.theStore = {}
        self.theWaitingList = {}
        self.lock = threading.Lock()
        self.parser = Parser()
        
    def insertPid(self, functor, si, pid):
#        with self.lock:
            if functor in self.theWaitingList.keys():
               self.theWaitingList[functor].append((pid,si))
            else:
               self.theWaitingList.update({ functor: [(pid,si)]})

    def wakeUpOnNewSI(self, functor):
#        with self.lock:        
            if functor in self.theWaitingList.keys():
               for pid, si in self.theWaitingList[functor]:
                  if functor in self.theStore.keys():
                    bool_res,si_res = self.is_si_in_dict(si,self.theStore[functor])
                    if bool_res:
                       pid.send((str(si_res) + " now present").encode("utf-8"))
                       (self.theWaitingList[functor]).remove((pid,si))                           

    # function tell(functor, si)
    # --------------------------
    #
    # add functor as a key of store if necessary
    # and associate si with functor
    #
    # functor and si are strings
    # functor is the functor of si
    
    def tell(self, functor, si, pid):
        with self.lock:
            if functor in self.theStore.keys():
                if si in self.theStore[functor]:
                    (self.theStore[functor])[si] = (self.theStore[functor])[si] +1
                    pid.send((str(si) + " told").encode("utf-8"))
                    self.wakeUpOnNewSI(functor)
                    return (True, str(si) + " told")
                else:
                    (self.theStore[functor]).update({ si: 1})
                    pid.send((str(si) + " told").encode("utf-8"))
                    self.wakeUpOnNewSI(functor)
                    return (True, str(si) + " told")                
            else:
                self.theStore.update({ functor: { si : 1} })
                pid.send((str(si) + " told").encode("utf-8"))
                self.wakeUpOnNewSI(functor)
                return (True, str(si) + " told")                

    # function partial_match(si1,si2)
    # -------------------------------
    #
    # check whether si1 (partially) match si2
    #
    # si1 and si2 are string representation of si-terms
            
    def partial_match(self, si_told, si_asked):
        ast_told = self.parser.parse_augsiterm(si_told)
        uast_told = ast_told.convert_to_si_composed()
        # uast_told = ast_told
        fct_told = uast_told.functor
        args_told = uast_told.arguments
        ast_asked = self.parser.parse_augsiterm(si_asked)
        uast_asked = ast_asked.convert_to_si_composed()
        # uast_asked = ast_asked
        fct_asked = uast_asked.functor
        args_asked = uast_asked.arguments
        if (fct_asked == fct_asked):
            return self.partial_match_list(args_told,args_asked)
        else:
            return False

    def partial_match_list(self,args_told,args_asked):
        res = True
        if len(args_asked) <= len(args_told):
            for i in range(len(args_asked)):
               if res:
                  res = (args_asked[i] == args_told[i])
            return res
        else:
            return False

        
    # function is_si_in_dict(si,dict)
    # -------------------------------
    #
    # check whether si partially match one of the keys of dict
    # if so return True together with the first key found
    # otherwise return False with si
    #
    # si is the string representation of a si-term
    # dict is a dictionary mapping strings to integers
        
    def is_si_in_dict(self,si,dict):
        res = False
        found_si = si
        for k in dict.keys():
            print(f"k = {k}")
            if (not res):
                res = self.partial_match(k,si)
                if res: found_si = k
        return (res,found_si)


    
    # function ask(functor, si)
    # --------------------------
    #
    # check whether si is in the store
    # if so return True with the string representation of the
    # found si-term (partially) matching si
    #
    # functor and si are strings
    # functor is the functor of si
    
    def ask(self, functor, si, pid):
        with self.lock:        
            if functor in self.theStore.keys():
                bool_res,si_res = self.is_si_in_dict(si,(self.theStore)[functor])
                if bool_res:
                    pid.send((str(si_res) + " present").encode("utf-8"))
                    return (bool_res,str(si_res))
                else:
                    self.insertPid(functor,si,pid)
                    return (False, "ask(" + str(si) +") failed")
            else: 
                self.insertPid(functor,si,pid)                
                return (False, "ask(" + str(si) +") ff failed")


    def reset_store(self,pid):
        self.theStore = {}
        self.theWaitingList = {}
        pid.send(("store reset").encode("utf-8"))
        return (True, "store reset")


# To be completed            
#    def get(self, si):
#        if si in self.theStore.keys():
#            if self.theStore[si] >= 1:
#                self.theStore[si] = self.theStore[si]-1
#                return (True, str(si) + " successfully got")
#            else:
#                return (False, "get(" + str(si) +") failed")
#        else:
#            return False
#        
#    def nask(self, si):
#        if si in self.theStore.keys():
#            if (self.theStore[si] == 0):
#                return (True, str(si) + " not present")
#            else:
#                return (False, "nask(" + str(si) +") failed")
#        else:
#            return (True, str(si) + " not present")
#
#    def print_store(self):
#        return (True, str(self.theStore))
