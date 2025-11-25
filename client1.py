# clipopper.py
# ------------------------------------------------------
#   FILP Distributed Client using BLPy protocol
# ------------------------------------------------------

import socket
from parser import Parser
from data_structures import SI_PRGM
from popper.tester import Tester
from popper.core import Clause, Literal
from popper.loop import decide_outcome
from popper.util import Settings, Stats
from popper.util import load_kbpath
import re

# ======================================================
#  Helper: parse Popper rule string
# ======================================================

kbpath = "part1"
bk_file, ex_file, bias_file = load_kbpath(kbpath)

# 🔹 Initialize ILP settings
settings = Settings(bias_file, ex_file, bk_file)
tester = Tester(settings)
stats  = Stats(log_best_programs=settings.info)

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


def initialisation():
    global client_id, path_dir
    print("Please introduce ... ")
    client_id = input("- the number to identify the client: ")
    path_dir = input("- the path to example files (folder): ")
    # LOAD PROLOG BACKGROUND + EXAMPLES
    bk, ex, bias = load_kbpath(path_dir)
    settings = Settings(bias, ex, bk)
    tester = Tester(settings)
    stats = Stats(log_best_programs=settings.info)
    settings.num_pos, settings.num_neg = len(tester.pos), len(tester.neg)

def transform_rule(rule_str):
    rule_str = rule_str.strip()
    if rule_str.endswith('.'):
        rule_str = rule_str[:-1]

    head_part, body_part = rule_str.split(":-")
    head = Literal.from_string(head_part.strip())

    body_lits = re.findall(r'\w+\(.*?\)', body_part)
    body = tuple(Literal.from_string(b) for b in body_lits)

    return (head, body)

def test_rules_locally(hypothesis):
    rules = [transform_rule(r) for r in hypothesis]
    cm = tester.test(rules)
    outcome = decide_outcome(cm)
    return outcome[0].name.lower(), outcome[1].name.lower()

def send_epair(sock, client_id, Eplus, Eminus):
    msg = f"tell(epair({client_id},{Eplus},{Eminus}))"
    sock.send(msg.encode())
    sock.recv(1024)
def popper_read_hypothesis(sock):
    """Reads hypothesis rules sent by server via BLPy protocol."""

    # DEMANDE prgmlen
    sock.send(b"ask(prgmlen)")
    resp = sock.recv(1024).decode()
    print("Raw Received:", resp)

    # Extraire prgmlen(N)
    match = re.search(r"prgmlen\((\d+)\)", resp)
    if not match:
        print("Could not extract prgmlen")
        return []
    nb_cl = int(match.group(1))
    print(f"nb_cl = {nb_cl}")

    clauses = []

    # Pour chaque clause : ask(prgm(i))
    for i in range(nb_cl):
        sock.send(f"ask(prgm({i}))".encode())
        resp = sock.recv(1024).decode()
        print("Raw Clause:", resp)

        # Extraire le bloc { ... }
        m = re.search(r"\{(.*)\}", resp)
        if not m:
            print("Could not extract rule body")
            continue

        raw_rule = m.group(1).strip()

        # Normaliser la syntaxe Popper :
        # - enlever espaces inutiles
        # - s'assurer du point final
        clean_rule = raw_rule.strip()
        if not clean_rule.endswith("."):
            clean_rule += "."

        print("➡️ Parsed rule:", clean_rule)
        clauses.append(clean_rule)

    return clauses



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


def send_epair(sock, client_id, Eplus, Eminus):
    msg = f"tell(epair({client_id},{Eplus},{Eminus}))"
    sock.send(msg.encode())
    _ = sock.recv(1024)


def check_finish():
    return input("Finish? (0=no, 1=yes): ") == "1"


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
        
        while not finish:

            # 1) RECEIVE RULES
            hypothesis = popper_read_hypothesis(sock)
            print("\nReceived hypothesis:")
            for h in hypothesis:
                print("   ", h)

            # 2) LOCAL TESTING
            Eplus, Eminus = popper_test_local(hypothesis, tester)
            print(f"Local outcome = ({Eplus}, {Eminus})")

            # 3) SEND OUTCOME TO SERVER
            send_epair(sock, client_id, Eplus, Eminus)

            finish = check_finish()

    except Exception as e:
        print("Error:", e)

    finally:
        sock.close()
        print("Connection closed.")


myparser = Parser()
client_id = "0"
path_dir = "."
run_client()
