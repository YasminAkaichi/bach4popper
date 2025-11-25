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

import parsimonious
from parsimonious.grammar import Grammar


GRAMMAR = Grammar(
    r"""    

    # ----------------------------------------------------------- #
    #                                                             #
    #                      BASIC ELEMENTS                         #
    #                                                             #
    #  Note : \w matches any word character (ie a-zA-Z0-9_)       #
    #         \s matches any white space                          #
    #                      (ie space itself, \n, \r, \t, \f)      #
    #                                                             #
    # ----------------------------------------------------------- #
    
    lc_word   = ~"[a-z]\w*"       # word starting with lower case letter
    uc_word   = ~"[A-Z]\w*"       # word starting with upper case letter
    ac_word   = ~"[a-zA-Z0-9]\w*" # word starting with any letter or digit
    __        = ~"\s*"            # whitespaces
    integer   = ~"\d+"            # integer


    # ----------------------------------------------------------- #
    #                                                             #
    #                 STRUCTURE INFORMATION TERMS                 #
    #                                                             #
    # ----------------------------------------------------------- #
    
    extInfo        =  stInfo / augStInfo / stPrgm / stTheories 

    stInfo        =  ac_word ( stInfoArgs )?
    stInfoArgs    =  "(" __ stLInfoArgs __ ")"
    stLInfoArgs   =  stInfo __ ("," __ stInfo __)* 

    stPrgm        =  "{" __ stLHornClause __ "}"
    stLHornClause =  stHornClause __ (";" __ stHornClause __)*
    stHornClause  =  headClause (bodyClause)? __ "."
    headClause    =  stInfo
    bodyClause    =  __ ":-" __ stLInfoArgs

    stTheories    =  "[" __ stLPrgm __ "]"
    stLPrgm       =  stPrgm __ (";" __ stPrgm __)*

    augStInfo     =  ac_word ( augStInfoArgs )?
    augStInfoArgs =  "(" __ augStLInfoArgs  __ ")"
    augStLInfoArgs = extInfo __ ("," __ extInfo __)*

    comAugStInfo  = augStInfo ( lComments )?
    lComments     =  ( __ ac_word )*

    # siOnStore     =  stInfo / stiPrgm / stiTh
    # stiPrgm       =  "prgm(" __ stPrgm __ ")"
    # stiTh         =  "theories(" __ stTheories __ ")"


    # ----------------------------------------------------------- #
    #                                                             #
    #                          PRIMITIVES                         #
    #                                                             #
    # ----------------------------------------------------------- #
    
    primitive  = tell / ask / reset

    tell   =  "tell(" __ augStInfo __ ")"
    ask    =  "ask("  __ augStInfo __ ")"
    reset  =  "reset"

    shPrimitive = tellprgm / askprgm / tellth / askth

    tellprgm = "tellprgm(" __ stPrgm __ ")"
    askprgm = "askprgm()"

    tellth = "tellth(" __ stTheories __ ")"
    askth = "askth()"


    # ----------------------------------------------------------- #
    #                                                             #
    #                         CLOSE ACTION                        #
    #                                                             #
    # ----------------------------------------------------------- #

    close = "close"
    
    # ----------------------------------------------------------- #
    #                                                             #
    #                          BLPy ENTRY                         #
    #                                                             #
    # ----------------------------------------------------------- #

    blpy_entry = primitive / shPrimitive / close

    """ 
)


