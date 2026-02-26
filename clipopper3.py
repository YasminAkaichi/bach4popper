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
import json 
import os
import traceback

CLIENT_ID = 3

#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/iggp-rps_part3"
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/zendo1_part3"
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/trains_part3"


import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "zendo1_part3")


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

def count_pos_neg_in_file(ex_file: str):
    pos = neg = 0
    with open(ex_file, "r") as f:
        for line in f:
            s = line.strip()
            if s.startswith("pos("):
                pos += 1
            elif s.startswith("neg("):
                neg += 1
    return pos, neg




def initialisation():
    #global client_id, path_dir
    print("Please introduce ... ")
    #client_id = input("- the number to identify the client: ")
    #path_dir = input("- the path to example files (folder): ")
    client_id = int(CLIENT_ID)
    path_dir = DATASET_PATH
    
    #LOAD PROLOG BACKGROUND + EXAMPLES
    bk, ex, bias = load_kbpath(path_dir)
    settings = Settings(bias, ex, bk)
    tester = Tester(settings)
    stats = Stats(log_best_programs=settings.info)
    settings.num_pos, settings.num_neg = len(tester.pos), len(tester.neg)
    # 🔎 DEBUG: compare FILE vs TESTER
    # 🔎 DEBUG: compare FILE vs TESTER
    file_pos, file_neg = count_pos_neg_in_file(ex)
    print(f"[CLIENT {client_id}] FILE counts   pos={file_pos} neg={file_neg}")
    print(f"[CLIENT {client_id}] TESTER counts pos={len(tester.pos)} neg={len(tester.neg)}")
    return client_id, path_dir, settings, tester, stats




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

def format_conf_matrix(conf_matrix):
    tp, fn, tn, fp = conf_matrix

    precision = 'n/a'
    if (tp + fp) > 0:
        precision = f'{tp / (tp + fp):0.2f}'

    recall = 'n/a'
    if (tp + fn) > 0:
        recall = f'{tp / (tp + fn):0.2f}'

    accuracy = 'n/a'
    total = tp + tn + fp + fn
    if total > 0:
        accuracy = f'{(tp + tn) / total:0.2f}'

    return (
        f'% Precision:{precision}, Recall:{recall}, Accuracy:{accuracy}, '
        f'TP:{tp}, FN:{fn}, TN:{tn}, FP:{fp}\n'
    )


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
        print(format_conf_matrix(cm))
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
    score_int = int(float(score)) 
    msg = f"tell(epair({tour},{client_id},{Eplus},{Eminus},{score_int}))"
    sock.send(msg.encode())
    sock.recv(1024)  # confirmation du store


def check_finish():
    return input("Finish? (0=no, 1=yes): ") == "1"


    
import re
def popper_read_hypothesis(sock, tour):
    # 1) non bloquant : est-ce final ?
    sock.send(f"in(prgmlen({tour},final))".encode())
    is_final = sock.recv(1024).decode().strip().lower() == "true"

    if is_final:
        # final round => lire clauses jusqu'à échec
        clauses = []
        i = 0
        while True:
            sock.send(f"ask(prgm({tour},{i}))".encode())
            resp = sock.recv(4096).decode()
            if "failed" in resp or "wait" in resp:
                break
            m2 = re.search(r"\{\s*(.*?)\s*\}", resp)
            if not m2:
                break
            rule = m2.group(1).strip()
            if not rule.endswith("."):
                rule += "."
            clauses.append(rule)
            i += 1
        return clauses, "final"

    # 2) sinon, round normal (bloquant)
    sock.send(f"ask(prgmlen({tour}))".encode())
    resp = sock.recv(1024).decode()

    m = re.search(r"prgmlen\(\s*"+str(tour)+r"\s*,\s*(\w+|-?\d+)\s*\)", resp)
    if not m:
        return [], 0

    nb_cl = int(m.group(1))
    clauses = []
    for i in range(nb_cl):
        sock.send(f"ask(prgm({tour},{i}))".encode())
        resp = sock.recv(4096).decode()
        m2 = re.search(r"\{\s*(.*?)\s*\}", resp)
        if m2:
            rule = m2.group(1).strip()
            if not rule.endswith("."):
                rule += "."
            clauses.append(rule)
    return clauses, nb_cl


def popper_read_hypothesisold(sock, tour):
    sock.send(f"ask(prgmlen({tour}))".encode())
    resp = sock.recv(1024).decode()

    m = re.search(r"prgmlen\(\s*"+str(tour)+r"\s*,\s*(\w+|-?\d+)\s*\)", resp)
    if not m:
        return [], 0

    nb_raw = m.group(1).lower()

    is_final = (nb_raw == "final")

    clauses = []

    if is_final:
        i = 0
        while True:
            sock.send(f"ask(prgm({tour},{i}))".encode())
            resp = sock.recv(4096).decode()

            if "failed" in resp or "wait" in resp:
                break

            m2 = re.search(r"\{\s*(.*?)\s*\}", resp)
            if not m2:
                break

            rule = m2.group(1).strip()
            if not rule.endswith("."):
                rule += "."
            clauses.append(rule)
            i += 1

        return clauses, "final"

    # NORMAL
    nb_cl = int(nb_raw)
    for i in range(nb_cl):
        sock.send(f"ask(prgm({tour},{i}))".encode())
        resp = sock.recv(4096).decode()
        m2 = re.search(r"\{\s*(.*?)\s*\}", resp)
        if m2:
            rule = m2.group(1).strip()
            if not rule.endswith("."):
                rule += "."
            clauses.append(rule)

    return clauses, nb_cl

def popper_read_hypothesis1513(sock, tour):
    # get prgmlen(tour, N)
    query = f" ask(prgmlen({tour})) "
    sock.send(query.encode())
    resp = sock.recv(1024).decode()

    #si tour = 0 

    print("Raw prgmlen:", resp)

    # parse N
    m = re.search(r"prgmlen\(\s*"+str(tour)+r"\s*,\s*(-?\d+)\s*\)", resp)
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

    return clauses, nb_cl

def is_final_round(sock):
    sock.send(f"ask(final({0}))".encode())
    resp = sock.recv(1024).decode()
    return "final" in resp

def run_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 8000))

    try:
        cli_prompt()
        client_id, path_dir, settings, tester, stats = initialisation()

        tour = 0
        final_round = False

        while True:
            hypothesis, nb_raw = popper_read_hypothesis(sock, tour)

            # 🔴 FINAL
            if nb_raw == "final":
                print("\n🎉 FINAL round detected")
                print("Final hypothesis:")
                for h in hypothesis:
                    print("  ", h)
                break

            # 🟢 NORMAL
            nb_cl = nb_raw
          

            print("\nReceived hypothesis:")
            for h in hypothesis:
                print("   ", h)


            # --------------------------------------------------
            # 5) Normal round → local test
            # --------------------------------------------------
            Eplus, Eminus, score = popper_test_hypothesis_final(
                hypothesis, tester
            )

            print(f"Local outcome = ({Eplus}, {Eminus}), score={score}")

            # --------------------------------------------------
            # 6) Send feedback
            # --------------------------------------------------
            send_epair(sock, client_id, tour, Eplus, Eminus, score)

            tour += 1

    except Exception as e:
        print("Client error:", e)

    finally:
        #sock.close()
        sock.send(b"close")
        sock.recv(1024)
        print("Connection closed.")


def run_clientxx():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 8000))

    try:
        cli_prompt()
        client_id, path_dir, settings, tester, stats = initialisation()

        tour = 0
        final_round = False

        while True:
            # --------------------------------------------------
            # 1) Ask for current round info
            # --------------------------------------------------
            #sock.send(f"ask(round({tour}))".encode())
            #resp = sock.recv(1024).decode()

            
            #print("Raw prgmlen:", resp)

            # 3) CAS FINAL
         
            hypothesis, nb_cl = popper_read_hypothesis(sock, tour)
            
            if nb_cl == "final":
                print("\n🎉 FINAL round detected")
                print("Final hypothesis:")
                for h in hypothesis:
                    print("   ", h)
                break


        
            # --------------------------------------------------
            # 5) Normal round → local test
            # --------------------------------------------------
            Eplus, Eminus, score = popper_test_hypothesis_final(
                hypothesis, tester
            )

            print(f"Local outcome = ({Eplus}, {Eminus}), score={score}")

            # --------------------------------------------------
            # 6) Send feedback
            # --------------------------------------------------
            send_epair(sock, client_id, tour, Eplus, Eminus, score)

            # attendre que le prochain round soit publié
            next_round = tour + 1

            sock.send(f"ask(round({next_round}))".encode())
            resp = sock.recv(1024).decode()

            if "present" in resp:
                tour = next_round
            else:
                print("No next round → server finished.")
                break

    except Exception as e:
        print("Client error:", e)

    finally:
        #sock.close()
        #print("Connection closed.")
        try:
            sock.send(b"close")
            sock.recv(1024)
        except Exception:
            pass
        sock.close()
        print("Connection closed.")


#myparser = Parser()
#client_id = "0"
#path_dir = "."

#run_client()

if __name__ == "__main__":
    run_client()