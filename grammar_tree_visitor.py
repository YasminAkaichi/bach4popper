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


 Implementation note :

 This file defines the grammar used by the parser.Parser object.
 To that end the parsimonious library is used. For details, see

 https://github.com/erikrose/parsimonious

"""

from parsimonious.nodes import NodeVisitor

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


class Visitor(NodeVisitor):
    """ Grammar tree visitor for the BLPy grammar (see file grammar.py)

    This class is used conjointly with the grammar.GRAMMAR to parse some text.

        tree = grammar.GRAMMAR.parse(text)    
             # Reads the input string and outputs a tree
        obj  = grammar_tree_visitor.Visitor().visit(tree)  
             # Navigates the tree and outputs a usable object
    
    Methods
    -------
    visit_myrule(node, visited_children)
        Visits one node of the parse tree that corresponds to a grammatical rule

        Parameters
        ----------
        node
            The node we're visiting
        visited_children
            The results of visiting the children of that node, in a list           
    """
    
    
    # -------------------------------------------------------------- #
    #                                                                #
    #                       Generic visits                           #
    #                                                                #
    # -------------------------------------------------------------- #
            
    def generic_visit(self, node, visited_children):
        """ The default visit method. """
        return visited_children or node.text
    
    def visit_choice(self, node, visited_children): 
        """ When visiting a choice, return the only element in visited_children """
        choice, = visited_children
        return choice
    
    def visit_leaf(self, node, visited_children) -> str: 
        """ When visiting a leaf, return the text matched by the regex expression """
        return node.text


    # -------------------------------------------------------------- #
    #                                                                #
    #                       Basic elements                           #
    #                                                                #
    # -------------------------------------------------------------- #

    visit_lc_word    = visit_leaf
    visit_uc_word    = visit_leaf    
    visit_ac_word    = visit_leaf
    visit_integer    = lambda self, node, _: int(  node.text)
    

    # extInfo        =  stInfo / augStInfo / stPrgm / stTheories
    visit_extInfo = visit_choice
    
    # stInfo        =  ac_word ( stInfoArgs )?
    def visit_stInfo(self, node, visited_children) -> Abs_SITerm:
        lcw, opt_stInfoArgs = visited_children
        if not opt_stInfoArgs:
            return SI_ATOMIC(lcw) 
            # return SI_COMPOSED(lcw,[])
        else:
            return SI_COMPOSED(lcw,opt_stInfoArgs[0])

    # stInfoArgs    =  "(" __ stLInfoArgs __ ")"
    def visit_stInfoArgs(self, node, visited_children) -> list:
        _, _, stargs, _, _ = visited_children
        return stargs

    # stLInfoArgs   =  stInfo __ ("," __ stInfo __)* 
    def visit_stLInfoArgs(self, node, visited_children) -> list:
        si, _, opt_lsi = visited_children
        l_si_terms = [si] + [t for _, _, t, _ in opt_lsi]
        return l_si_terms

    # stPrgm        =  "{" __ stLHornClause __ "}"
    def visit_stPrgm(self, node, visited_children) -> Abs_SITerm:
        _, _, stargs, _, _ = visited_children
        return SI_PRGM(stargs)
    
    # stLHornClause =  stHornClause __ (";" __ stHornClause __)*
    def visit_stLHornClause(self, node, visited_children) -> list:
        hc, _, opt_lhc = visited_children
        lhc = [hc] + [x for _, _, x, _ in opt_lhc]
        return lhc

    # stHornClause  =  headClause (bodyClause)? __ "."
    def visit_stHornClause(self, node, visited_children) ->  Abs_SITerm:
        head, opt_body, _, _ = visited_children
        if not opt_body:
            return SI_HORN_CLAUSE(head,[])
        else:
            return SI_HORN_CLAUSE(head,opt_body[0])

    # headClause    =  stInfo
    visit_headClause = visit_stInfo
    
    # bodyClause    =  __ ":-" __ stLInfoArgs
    def visit_bodyClause(self, node, visited_children) -> list:
        _, _, _, largs = visited_children
        return largs

    # stTheories    =  "[" __ stLPrgm __ "]"
    def visit_stTheories(self, node, visited_children) -> list:
        _, _, stargs, _, _ = visited_children
        return SI_THEORIES(stargs)

    # stLPrgm       =  stPrgm __ (";" __ stPrgm __)*
    def visit_stLPrgm(self, node, visited_children) -> list:
        th, _, opt_lth = visited_children
        lth = [th] + [x for _, _, x, _ in opt_lth]
        return lhc
   
    # augStInfo     =  ac_word ( augStInfoArgs )?
    def visit_augStInfo(self, node, visited_children) -> Abs_SITerm:
        lcw, opt_augStInfoArgs = visited_children
        if not opt_augStInfoArgs:
            return SI_ATOMIC(lcw) 
            # return SI_COMPOSED(lcw,[])
        else:
            return SI_COMPOSED(lcw,opt_augStInfoArgs[0])
    
    # augStInfoArgs =  "(" __ augStLInfoArgs  __ ")"
    def visit_augStInfoArgs(self, node, visited_children) -> list:
        _, _, stargs, _, _ = visited_children
        return stargs

    # augStLInfoArgs = extInfo __ ("," __ extInfo __)*
    def visit_augStLInfoArgs(self, node, visited_children) -> list:
        si, _, opt_lasi = visited_children
        l_asi_terms = [si] + [t for _, _, t, _ in opt_lasi]
        return l_asi_terms

    # comAugStInfo  = augStInfo ( lComments )?
    def visit_comAugStInfo(self, node, visited_children) -> Abs_SITerm:
        asi, opt_augStInfoArgs = visited_children
        return asi
    
    # lComments     =  ( __ ac_word )*
    def visit_lComments(self, node, visited_children) -> list:
        opt_lc = visited_children
        l_lc = [t for _, t in opt_lc]
        return l_lc

    
    
    # ----------------------------------------------------------- #
    #                                                             #
    #                          PRIMITIVES                         #
    #                                                             #
    # ----------------------------------------------------------- #
    
    # primitive  = tell / ask / reset
    visit_primitive = visit_choice

    # tell   =  "tell(" __ augStInfo __ ")"
    def visit_tell(self, node, visited_children) -> AST_PRIMITIVE:
        _, _, si, _, _ = visited_children
        return AST_PRIMITIVE("tell",si)
    
    # ask    =  "ask("  __ augStInfo __ ")"
    def visit_ask(self, node, visited_children) -> AST_PRIMITIVE:
        _, _, si, _, _ = visited_children
        return AST_PRIMITIVE("ask",si)

    # reset  =  "reset"
    def visit_reset(self, node, visited_children) -> AST_PRIMITIVE:
        si = SI_ATOMIC("none")
        return AST_PRIMITIVE("reset",si)

    # shPrimitive = tellprgm / askprgm / tellth / askth
    visit_shPrimitive = visit_choice

    # tellprgm = "tellprgm(" __ stPrgm __ ")"
    def visit_tellprgm(self, node, visited_children) -> AST_PRIMITIVE:
        _, _, stp, _, _ = visited_children
        return AST_PRIMITIVE("tellprgm",stp)
        
    # askprgm = "askprgm()"
    def visit_askprgm(self, node, visited_children) -> AST_PRIMITIVE:
        si = SI_ATOMIC("none")
        return AST_PRIMITIVE("askprgm",si)

    # tellth = "tellth(" __ stTheories __ ")"
    def visit_tellth(self, node, visited_children) -> AST_PRIMITIVE:
        _, _, sth, _, _ = visited_children
        return AST_PRIMITIVE("tellth",sth)
        
    # askth = "askth()"
    def visit_askth(self, node, visited_children) -> AST_PRIMITIVE:
        si = SI_ATOMIC("none")
        return AST_PRIMITIVE("askth",si)


    # ----------------------------------------------------------- #
    #                                                             #
    #                             CLOSE                           #
    #                                                             #
    # ----------------------------------------------------------- #

    # close = "close"
    def visit_close(self, node, visited_children) -> AST_CLOSE_FUNCTION:
        return AST_CLOSE_FUNCTION("close",[])

    

    

    # ----------------------------------------------------------- #
    #                                                             #
    #                          BLPy ENTRY                         #
    #                                                             #
    # ----------------------------------------------------------- #

    visit_blpy_entry = visit_choice
    
