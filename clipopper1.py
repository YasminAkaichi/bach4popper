# clipopper.py
# ------------------------------------------------------
#   FILP Distributed Client using BLPy protocol
# ------------------------------------------------------

import socket
from parser import Parser
from data_structures import SI_PRGM
from popper.tester import Tester
from popper.core import Clause, Literal
from popper.loop import decide_outcome, calc_score
from popper.util import Settings, Stats
from popper.util import load_kbpath
import re

import traceback
# ======================================================
#  Helper: parse Popper rule string
# ======================================================

#kbpath = "part1"
#bk_file, ex_file, bias_file = load_kbpath(kbpath)

# 🔹 Initialize ILP settings
#settings = Settings(bias_file, ex_file, bk_file)
#tester = Tester(settings)
#stats  = Stats(log_best_programs=settings.info)
DATASET_PATH = "datasets/part1"
CLIENT_ID = "1"
from parser import Parser

def parse_rule(rule_str):
    """Convert 'h(A):-b1(B),b2(C).' into Popper structure."""
    rule_str = rule_str.strip()
    if rule_str.endswith('.'):
        rule_str = rule_str[:-1]

    if ":-" in rule_str:
        head, body = rule_str.split(":-")
        body_lits = re.findall(r'\w+\(.*?\)', body)
        head = Literal.from_string(head.strip())
        body = tuple(Literal.from_string(b.strip()) for b in body_lits)
    else:
        head = Literal.from_string(rule_str)
        body = tuple()

    return (head, body)

# ======================================================
#  BLPy parsing helpers
# ======================================================

def get_nb_clause_from_prgmlen_si(ast):
    """Extract integer n from SI-term prgmlen(n)."""
    try:
        term = ast.arguments[0]
        if hasattr(term, "value"):
            return int(term.value)      # SI_ATOMIC case
        return int(str(term))
    except Exception as e:
        print(f"[ERROR extracting prgmlen] {e}")
        return 0

# ======================================================
#  CLIENT LOGIC
# ======================================================

def cli_prompt():
    print(r"""
 __ .   .__                
/  `|*  [__) _ ._ ._  _ ._.
\__.||  |   (_)[_)[_)(/,[  
               |  |        
""")


def initialisationold():
    global client_id, path_dir
    print("Please introduce ... ")
    client_id = input("- the number to identify the client: ")
    path_dir = input("- the path to example files (folder): ")
    #LOAD PROLOG BACKGROUND + EXAMPLES
    bk, ex, bias = load_kbpath(path_dir)
    settings = Settings(bias, ex, bk)
    tester = Tester(settings)
    stats = Stats(log_best_programs=settings.info)
    settings.num_pos, settings.num_neg = len(tester.pos), len(tester.neg)

def initialisation():
    global client_id, path_dir
    client_id = CLIENT_ID
    path_dir = DATASET_PATH

    print(f"[CLIENT {client_id}] Using dataset {path_dir}")

    bk, ex, bias = load_kbpath(path_dir)
    settings = Settings(bias, ex, bk)
    tester = Tester(settings)
    settings.num_pos, settings.num_neg = len(tester.pos), len(tester.neg)
    print(f"[CLIENT {client_id}] #POS={len(tester.pos)} #NEG={len(tester.neg)}")

def transform_rule_to_tester_format(rule_str):
    print(f"🔍 Transforming rule: {rule_str}")

    try:
        # Split head and body correctly
        head_body = rule_str.split(":-")
        if len(head_body) != 2:
            raise ValueError(f"Invalid rule format: {rule_str}")

        head_str = head_body[0].strip()
        body_str = head_body[1].strip()

        # *Fix: Properly extract body literals using regex**
        body_literals = re.findall(r'\w+\(.*?\)', body_str)

        print(f"Parsed head: {head_str}")
        print(f"Parsed body literals: {body_literals}")

        # Convert to Literal objects (assuming `Literal.from_string` exists)
        head = Literal.from_string(head_str)
        body = tuple(Literal.from_string(lit) for lit in body_literals)

        formatted_rule = (head, body)
        print(f"Formatted rule: {formatted_rule}")

        return formatted_rule
    except Exception as e:
        print(f"Error transforming rule: {rule_str} → {e}")
        return None  # Return None to indicate failure



def transform_rule(rule_str):
    """
    Transforme une règle string reçue du STORE en 
    structure Popper valide : (Literal, tuple(Literal)).
    """

    # nettoyer
    rule_str = rule_str.strip()

    # enlever le point final
    if rule_str.endswith('.'):
        rule_str = rule_str[:-1]

    # séparer head :- body
    if ":-" not in rule_str:
        # fait rare: règle factuelle
        head = Literal.from_string(rule_str.strip())
        return (head, tuple())

    head_str, body_str = rule_str.split(":-")
    head_str = head_str.strip()
    body_str = body_str.strip()

    # EXTRACTION ROBUSTE des littéraux du body
    #  ⚠ même regex que dans Flower ⚠
    body_literals = re.findall(r'\w+\([^)]*\)', body_str)

    # convertir head + body
    try:
        head = Literal.from_string(head_str)
        body = tuple(Literal.from_string(lit) for lit in body_literals)
        return (head, body)

    except Exception as e:
        print("❌ transform_rule ERROR:", e)
        return None
    
def parse_rules(rule_str):
    rule_str = rule_str.strip()
    if rule_str.endswith('.'):
        rule_str = rule_str[:-1]

    head_str, body_str = rule_str.split(":-")

    head = Literal.from_string(head_str.strip())

    body_literals = re.findall(r'\w+\(.*?\)', body_str)
    body = tuple(Literal.from_string(bl) for bl in body_literals)

    # LA LIGNE LA PLUS IMPORTANTE :
    return Clause(head, body)

def parse_rule_popper(rule_str):
    """
    Transforme une règle sous forme string 'h(X):-b1(X),b2(Y).'
    vers un tuple Popper : (Literal, (Literal, Literal, ...))
    """
    rule = rule_str.strip()

    # remove trailing dot
    if rule.endswith('.'):
        rule = rule[:-1]

    # split head/body
    if ":-" in rule:
        head_str, body_str = rule.split(":-")
        body_literals = re.findall(r'\w+\(.*?\)', body_str)
    else:
        head_str = rule
        body_literals = []

    head = Literal.from_string(head_str.strip())
    body = tuple(Literal.from_string(b.strip()) for b in body_literals)

    return (head, body)


def test_hypothesis(rule_strings, tester):
    """
    Teste une hypothèse complète (une liste de clauses Popper).
    rule_strings = [
        "f(A) :- has_load(B,D),has_load(C,D), ... .",
        "f(A) :- has_load(D,C),triangle(B), ... .",
        "f(A) :- has_load(B,D),has_car(A,B), ... ."
    ]
    """
    try:
        rules = []

        for r in rule_strings:
            r = r.strip()
            if r.endswith('.'):
                r = r[:-1]

            if ":-" in r:
                head_str, body_str = r.split(":-")
            else:
                head_str = r
                body_str = ""

            head = Literal.from_string(head_str.strip())

            # parse body into literals
            body_literals = []
            if body_str.strip():
                for lit in body_str.split(","):
                    lit = lit.strip()
                    if lit:
                        body_literals.append(Literal.from_string(lit))

            rules.append((head, tuple(body_literals)))

        # Maintenant on teste TOUTES les clauses ensemble
        cm = tester.test(rules)
        Eplus, Eminus = decide_outcome(cm)

        return (
            str(Eplus).lower() if Eplus else "none",
            str(Eminus).lower() if Eminus else "none"
        )

    except Exception as e:
        print("Error while testing hypothesis:", e)
        return ("x", "x")

def popper_test_local(rule_strings, tester):
    """
    Compute (Eplus, Eminus) exactly as Popper.
    Rule_strings = ["f(A) :- ... ."]
    """
    try:
        rules = []
        for r in rule_strings:
            r = r.strip()
            if r.endswith('.'):
                r = r[:-1]

            if ":-" in r:
                head_str, body_str = r.split(":-")
                body_literals = re.findall(r'\w+\([^)]*\)', body_str)
            else:
                head_str = r
                body_literals = []

            head = Literal.from_string(head_str.strip())
            body = tuple(Literal.from_string(b.strip()) for b in body_literals)
            rules.append((head, body))

        cm = tester.test(rules)
        Eplus, Eminus = decide_outcome(cm)

        # NORMALISATION (clé du problème !)
        def norm(x):
            if hasattr(x, "name"):
                return x.name.lower()
            return str(x).lower()

        return norm(Eplus), norm(Eminus)

    except Exception as e:
        print("Local test failed:", e)
        return ("x", "x")




def get_nb_clause_from_prgmlen_si(ast):
    try:
        arg_prgmlen_si = ast.arguments
        nb_cl = arg_prgmlen_si[0]
        return nb_cl
    except Exception as e:
        print(f"Error: {e}")


import re

def transform_rule_to_tester_format(rule_str):
    head_body = rule_str.split(":-")
    if len(head_body) != 2:
        raise ValueError(f"Invalid rule format: {rule_str}")

    head_str = head_body[0].strip()
    body_str = head_body[1].strip()

    body_literals = re.findall(r'\w+\(.*?\)', body_str)

    head = Literal.from_string(head_str)
    body = tuple(Literal.from_string(lit) for lit in body_literals)

    return (head, body)

def popper_test_hypothesis_final(hypothesis_strings, tester):
    try:
        print("\n Starting local test of hypothesis...")
        print("Hypothesis strings:")
        for h in hypothesis_strings:
            print(" ", h)

        rules = []
        for rs in hypothesis_strings:
            formatted = transform_rule_to_tester_format(rs)
            if formatted is None:
                print(f"Failed to transform rule: {rs}")
                continue
            rules.append(formatted)

        #print(f"Total rules parsed: {len(rules)}")

        print(f"Total Pos examples: {len(tester.pos)}")
        print(f"Total Neg examples: {len(tester.neg)}")

        cm = tester.test(rules)

        print("Confusion matrix:", cm)

        Eplus, Eminus = decide_outcome(cm)
        print(f"Outcome = ({Eplus}, {Eminus})")
        score = calc_score(cm)

        return str(Eplus).lower(), str(Eminus).lower(), str(score).lower()

    except Exception as e:
        print("Error while testing hypothesis:")
        traceback.print_exc()
        return ("x", "x")


def popper_test_local(rule_strings, tester):
    if len(rule_strings) == 0:
        return ("none", "none")

    rules = [parse_rule(r) for r in rule_strings]
    print(f"ruuuuuuuuuuuuuuuules:{rules}")
    try:
        cm = tester.test(rules)
    except Exception as e:
        print("Tester failure:", e)
        return ("none", "none")
    out = decide_outcome(cm)
    print(f"outcome{out}")

    Eplus = out[0].name.lower()
    Eminus = out[1].name.lower()

    return (Eplus, Eminus)



def send_epair(sock, client_id, tour, Eplus, Eminus, score):
    msg = f"tell(epair({tour},{client_id},{Eplus},{Eminus},{score}))"
    sock.send(msg.encode())
    sock.recv(1024)  # confirmation du store


def check_finish():
    return input("Finish? (0=no, 1=yes): ") == "1"


    
import re


def popper_read_hypothesis(sock, tour):
    # get prgmlen(tour, N)
    query = f" ask(prgmlen({tour})) "
    sock.send(query.encode())
    resp = sock.recv(1024).decode()
    print("Raw prgmlen:", resp)

    # parse N
    m = re.search(r"prgmlen\(\s*"+str(tour)+r"\s*,\s*(\d+)\s*\)", resp)
    if not m:
        print("Could not extract prgmlen — maybe the STORE replied differently?")
        return []

    nb_cl = int(m.group(1))
    print(f"[CLIENT] nb_cl = {nb_cl}")

    clauses = []

    for i in range(nb_cl):
        #query = f" get(prgm({tour},{i})) "
        query = f" ask(prgm({tour},{i})) "

        sock.send(query.encode())
        resp = sock.recv(4096).decode()
        print("Raw clause:", resp)

        m = re.search(r"\{\s*(.*?)\s*\}", resp)
        if not m:
            print(" Could not extract clause")
            continue

        rule = m.group(1).strip()
        if not rule.endswith("."):
            rule += "."

        clauses.append(rule)

    return clauses




def run_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 8000))
    finish = False
    hypothesis = []

    try:
        cli_prompt()
        initialisation()

        # Load ILP data
        bk_file, ex_file, bias_file = load_kbpath(path_dir)
        settings = Settings(bias_file, ex_file, bk_file)
        tester = Tester(settings)
        settings.num_pos, settings.num_neg = len(tester.pos), len(tester.neg)
        tour = 0
        stats  = Stats(log_best_programs=settings.info)
        while True:
            msg = f"ask(round({tour}))"
            sock.send(msg.encode())
            sock.recv(1024)
            # 1) RECEIVE RULES
            hypothesis = popper_read_hypothesis(sock,tour)
            print("\nReceived hypothesis:")
            for h in hypothesis:
                print("   ", h)

            # 2) LOCAL TESTING
            Eplus, Eminus, score = popper_test_hypothesis_final(hypothesis, tester)

            print(f"Local outcome = ({Eplus}, {Eminus})")
         
            # 3) SEND OUTCOME TO SERVER
            send_epair(sock, client_id,tour, Eplus, Eminus, score)
            tour += 1
            #finish = check_finish()

    except Exception as e:
        print("Error:", e)

    finally:
        sock.close()
        print("Connection closed.")


myparser = Parser()
client_id = "0"
path_dir = "."
run_client()
