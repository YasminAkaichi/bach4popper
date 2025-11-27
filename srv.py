import socket
from popper.util import Settings, Stats
from popper.asp import ClingoSolver, ClingoGrounder
from popper.constrain import Constrain
from popper.tester import Tester
from popper.core import Clause
from aggstrategy import aggregate_outcomes, aggregate_popper

import numpy as np
from popper.structural_tester import StructuralTester

from popper.util import load_kbpath


OUTCOME_ENCODING = {"all": 1, "some": 2, "none": 3}
OUTCOME_DECODING = {1: "all", 2: "some", 3: "none"}
# ================================
#    GLOBAL STATE
# ================================
class FILPServerState:
    """Conserve TOUT l’état du solver entre les rounds."""

    def __init__(self, settings, solver, grounder, constrainer, tester, stats):
        self.settings = settings
        self.solver = solver
        self.grounder = grounder
        self.constrainer = constrainer
        self.tester = tester
        self.stats = stats

        self.current_hypothesis = None
        self.current_before = None
        self.current_min_clause = 0
        self.current_clause_size = 1
# ================================
#   UI
# ================================
def cli_prompt():
    banner = """
   _____               ____                             
  / ___/______   __   / __ \____  ____  ____  ___  _____
  \__ \/ ___/ | / /  / /_/ / __ \/ __ \/ __ \/ _ \/ ___/
 ___/ / /   | |/ /  / ____/ /_/ / /_/ / /_/ /  __/ /    
/____/_/    |___/  /_/    \____/ .___/ .___/\___/_/     
                              /_/   /_/                 
"""
    print(banner)


def convert_to_blpy(rule):
    r = rule.replace(" ", "")
    r = r.replace(":-", ",")
    r = r.replace("),", ");")
    if not r.endswith("."):
        r += "."
    return r
# ================================
#   SEND RULES TO CLIENT
# ================================


def tell_hypothesis(client, hyp):
    nb_cl = len(hyp)
    str_nb_cl = str(nb_cl)
    msg = f"tell( prgmlen({str_nb_cl}) )"
    client.send(msg.encode("utf-8")[:1024])
    client.recv(1024)
    for i in range(0,nb_cl):
        print("in loop")
        str_i = str(i)
        clause = "{" + hyp[i] + "}"
        #clause = hyp[i].replace(",", ";")
        print(f"clause = {clause}")
        msg = f"tell( prgm({str_i},{clause}) )"
        client.send(msg.encode("utf-8")[:1024])
        client.recv(1024)



def get_epsilon_pairs(client):
    pairs = []
    for i in range(1, nb_client + 1):
        msg = f"ask( epair({i}) )"
        client.send(msg.encode())
        resp = client.recv(1024).decode()
        pairs.append(resp)

    # After collecting ALL outcomes:
    client.send(b"reset")
    client.recv(1024)
    return pairs



def parse_epair(resp):
    # resp format: "epair(1,all,none)"
    parts = resp.strip().replace("epair(", "").replace(")", "").split(",")
    return parts[1], parts[2]   # (E+, E-)

def parse_epair(s):
    if not s or "(" not in s or ")" not in s:
        return ("none", "none")   # default safe outcome
    s = s.strip()
    inner = s[s.find("(")+1 : s.rfind(")")]
    parts = [p.strip() for p in inner.split(",")]
    if len(parts) < 3:
        return ("none", "none")
    return parts[1], parts[2]


def to_prolog_clause(rule):
    head, body = rule
    head_str = Clause.to_code(head)  # ex: f(A)
    body_strs = [Clause.to_code(b) for b in body]
    if body_strs:
        return f"{head_str} :- {', '.join(body_strs)}."
    else:
        return f"{head_str}."
    
def normalize_rule_for_store(rule_str):
    """
    Transforme une règle Popper 'f(A):-has_car(A);three_wheels(B)' 
    → 'f(A) :- has_car(A), three_wheels(B).'
    """

    # nettoyer espaces
    rule = rule_str.strip()

    # enlever point final s'il existe (on le remettra nous-même)
    if rule.endswith('.'):
        rule = rule[:-1]

    # *** Popper utilise parfois ';' au lieu de ',' ***
    rule = rule.replace(";", ",")

    # Ajouter espace autour de ':-'
    if ":-" in rule:
        head, body = rule.split(":-")
        rule = f"{head.strip()} :- {body.strip()}"
    else:
        # fait rare mais au cas où c’est un fact
        rule = rule.strip()

    # remettre un point final
    if not rule.endswith("."):
        rule += "."

    return rule

# ================================
#   MAIN LOOP
# ================================


def run_server():

    cli_prompt()
    print("Initialising FILP server...")

    nb_client = int(input("- number of Popper clients: "))
    path = input("- path to BK/Examples (folder): ")

    # ----------------------------------------------------------
    # POPPER INITIALISATION
    # ----------------------------------------------------------
    kbpath = f"{path}"
    _, _, bias_file = load_kbpath(kbpath)

    settings  = Settings(bias_file, None, None)
    stats     = Stats(log_best_programs=settings.info)
    solver    = ClingoSolver(settings)
    grounder  = ClingoGrounder()
    constrainer = Constrain()
    tester    = StructuralTester()

    # === Le vrai state (!!!)
    st = FILPServerState(settings, solver, grounder, constrainer, tester, stats)

    # ----------------------------------------------------------
    # Connect to STORE
    # ----------------------------------------------------------
    store = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    store.connect(("127.0.0.1", 8000))
    print("Connected to STORE.")

    # Initial outcomes (comme Flower)
    outcome_pair = ("none", "none")

    try:
        round_id = 0
        while True:

            print(f"\n========== ROUND {round_id} ==========")
            round_id += 1

            # ------------------------------------------------------
            # 1) POPPER ONE STEP
            # ------------------------------------------------------
            rules_arr, new_min, new_before, new_clause_sz, new_solver, solved, new_rules = aggregate_popper(
                outcome_pair,
                st.settings,
                st.solver,
                st.grounder,
                st.constrainer,
                st.tester,
                st.stats,
                st.current_min_clause,
                st.current_before,
                st.current_hypothesis,
                st.current_clause_size
            )

            # update FILP internal state
            st.current_min_clause = new_min
            st.current_before = new_before
            st.current_clause_size = new_clause_sz
            st.solver = new_solver
            
            if new_rules and len(new_rules[0])>0:
                st.current_hypothesis = new_rules 
            # Extraire règles Popper : strings utilisables par store
            
            rules_str = [Clause.to_code(r) for r in st.current_hypothesis] \
                        if st.current_hypothesis else []

            # Si aucune règle générée : STOP
            if not rules_arr or len(rules_arr[0]) == 0:
                print("No more rules produced. Stopping.")
                break

            raw_rules = rules_arr[0].tolist()

            # 2) Convertir en syntaxe BLPy pour le STORE
            rules_str = [normalize_rule_for_store(r) for r in raw_rules]
            print("Generated hypothesis (Store format):", rules_str)

            # 3) Envoi au STORE
            tell_hypothesis(store, rules_str)

            # =======================================================
            # 3) RÉCUPÉRER EPAIRS
            # =======================================================
            lepairs = get_epsilon_pairs(store)
            parsed = [parse_epair(e) for e in lepairs]

            Eplus, Eminus = aggregate_outcomes(parsed)
            print(f"Aggregated outcome = ({Eplus}, {Eminus})")

            # =======================================================
            # 4) CONDITION D'ARRÊT FILP
            # =======================================================
            if (Eplus, Eminus) == ("all", "none"):
                print(" Global solution found (ALL/NONE). Stopping.")
                break

    except Exception as e:
        print("Error:", e)

    finally:
        store.close()
        print("Connection to store closed.")



# ================================
#   RUN
# ================================
if __name__ == "__main__":
    nb_client = 0
    run_server()