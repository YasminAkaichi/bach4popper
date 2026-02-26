import socket
from popper.asp import ClingoSolver, ClingoGrounder
from popper.constrain import Constrain
from aggstrategy import aggregate_outcomes
import time
from popper.core import Clause
from popper.tester import Tester
from popper.util import load_kbpath, Settings, Stats
from popper.loop import build_rules, ground_rules
from popper.generate import generate_program

NB_CLIENTS = 3
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/iggp-rps"
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/zendo1"
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/trains"

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "zendo1")

# ================================
#    GLOBAL STATE
# ================================
class FILPServerState:
    """Conserve TOUT l’état du solver entre les rounds."""

    def __init__(self, settings, solver, grounder, constrainer, tester, stats, min_clause, before, clause_size, hypothesis):
        self.settings = settings
        self.solver = solver
        self.grounder = grounder
        self.constrainer = constrainer
        self.tester = tester
        self.stats = stats

        self.current_hypothesis = hypothesis
        self.current_before = before
        self.current_min_clause = min_clause
        self.current_clause_size = clause_size


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


def initialisation():
    print("Please introduce ...")
    nb_client = NB_CLIENTS 
    path_dir = DATASET_PATH
    return nb_client,path_dir

# ================================
#   POPPER INITIALISE
# ================================
def popper_initialisation(path_dir):
    #global settings, stats, solver, grounder, constrainer, tester
    #global current_hypothesis, current_before, current_min_clause, current_clause_size
     
    print("Initialising Distributed FILP...")

    # Load bias file only
    # The user provides a path where: BK, EX, BIAS normally exist
    # Here we assume bias.pl is inside that folder
    #bias_file = f"{path_dir}/bias.pl"
    
    #kbpath = f"{path_dir}"
    _, _, bias_file = load_kbpath(path_dir)
    settings = Settings(bias_file, None, None)
    stats = Stats(log_best_programs=settings.info)
    solver = ClingoSolver(settings)
    grounder = ClingoGrounder()
    constrainer = Constrain()
    tester = Tester(settings)
    #settings.num_pos, settings.num_neg = len(tester.pos), len(tester.neg)
    stats = Stats(log_best_programs=settings.info) 
    current_hypothesis = None
    current_before = None
    current_min_clause = 0
    current_clause_size = 0
    path_dir=path_dir
    state = FILPServerState(settings, solver, grounder, constrainer, tester, stats, current_min_clause, current_before, current_clause_size, current_hypothesis)
    return state 

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



def tell_hypothesis(store, hyp, tour):
    nb_cl = len(hyp)

    # prgmlen(tour, N)
    msg = f"tell(prgmlen({tour},{nb_cl}))"
    print("Sending:", msg)
    store.send(msg.encode())
    store.recv(1024)

    for i, clause in enumerate(hyp):
        clean = clause.strip()
        # on suppose qu'il y a déjà un point final ou pas, comme tu veux
        payload = "{" + clean + "}"

        msg = f"tell(prgm({tour},{i},{payload}))"
        print("Sending:", msg)
        store.send(msg.encode())
        store.recv(1024)



def get_epsilon_pairs(client, nb_client, tour):
    lepairs = []
    print(f"nb_client = {nb_client}")

    for i in range(1, nb_client + 1):

        while True:
            msg = f"ask(epair({tour},{i}))"
            client.send(msg.encode("utf-8")[:1024])
            response = client.recv(1024).decode("utf-8").strip()
            print("Response from store:", response)

            if "wait" in response or "failed" in response:
                time.sleep(0.05)  # AJOUT
                continue

            # ici, il y a bien un epair présent
            lepairs.append(response)
            break

    return lepairs



def normalize_rule_for_store(rule_str):
    """
    Transforme une règle Popper vers une version propre pour le STORE.
    Exemple :
        '{f(A) :- has_car(A,B),three_wheels(B).}'
    →      'f(A) :- has_car(A,B), three_wheels(B).'
    """

    # 1) Enlever les accolades { }
    rule = rule_str.replace("{", "").replace("}", "").strip()

    # 2) Nettoyer espaces
    if rule.endswith('.'):
        rule = rule[:-1]

    # 3) Convertir ';' en ','
    rule = rule.replace(";", ",")

    # 4) Assurer un format propre 'head :- body'
    if ":-" in rule:
        head, body = rule.split(":-", 1)
        rule = f"{head.strip()} :- {body.strip()}"
    else:
        rule = rule.strip()

    # 5) Remettre un point final
    if not rule.endswith("."):
        rule += "."

    return rule



def parse_epair_with_score(s):
    # expected: epair(round, client, Eplus, Eminus, score)
    if not s or "(" not in s or ")" not in s:
        return ("none", "none", 0.0)

    inner = s.strip()[s.find("(")+1 : s.rfind(")")]
    parts = [p.strip().lower() for p in inner.split(",")]

    if len(parts) >= 5:
        ep = parts[2]
        en = parts[3]
        try:
            score = float(parts[4])
        except:
            score = 0.0
        return (ep, en, score)

    # backward compatibility (no score)
    if len(parts) >= 4:
        return (parts[2], parts[3], 0.0)

    return ("none", "none", 0.0)


def reset_store(store):
    print("Resetting STORE")
    store.send(b"reset")
    store.recv(1024)

def reconstruct_conf_matrix(outcome, score, settings):
    """
    Reconstruit une confusion matrix cohérente pour Popper
    à partir de l'outcome fédéré.
    """

    num_pos = settings.num_pos
    num_neg = settings.num_neg

    Eplus, Eminus = outcome

    if (Eplus, Eminus) == ("all", "none"):
        tp = num_pos
        fn = 0
        tn = num_neg
        fp = 0

    elif Eplus == "all":
        tp = num_pos
        fn = 0
        tn = score - tp
        fp = num_neg - tn

    elif Eplus == "none":
        tp = 0
        fn = num_pos
        tn = score
        fp = num_neg - tn

    else:  # SOME / SOME etc.
        # Approximation cohérente pour Popper stats
        tp = score // 2
        tn = score - tp
        fn = num_pos - tp
        fp = num_neg - tn

    return (int(tp), int(fn), int(tn), int(fp))


def federated_test(program, store, nb_client, round_id):
    """
    Equivalent distribué de tester.test(program).
    Envoie l'hypothèse aux clients, récupère leurs évaluations
    et reconstruit outcome + score globaux.
    """

    # Convert program -> strings
    rules_str = [normalize_rule_for_store(Clause.to_code(cl)) for cl in program]

    # Publier l’hypothèse
    reset_store(store)
    store.send(f"tell(round({round_id}))".encode())
    store.recv(1024)

    tell_hypothesis(store, rules_str, round_id)

    # Récupérer feedback clients
    lepairs = get_epsilon_pairs(store, nb_client, round_id)
    parsed = [parse_epair_with_score(e) for e in lepairs]

    # Agrégation logique (ALL/SOME/NONE)
    eps_pairs = [(ep, en) for (ep, en, _) in parsed]
    outcome = aggregate_outcomes(eps_pairs)

    # Score Popper = somme (TP+TN)
    scores = [s for (_, _, s) in parsed]
    fed_score = sum(scores)

    return outcome, fed_score, rules_str

# ================================
#   MAIN LOOP
# ================================

def run_server():
    tFedPopper = 0.0
    tCentralPopper = 0.0

    cli_prompt()

    nb_client, path_dir = initialisation()
    st = popper_initialisation(path_dir)

    store = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    store.connect(("127.0.0.1", 8000))
    print("Connected to STORE.")

    best_score = None
    best_rules_str = None
    best_round = None

    round_id = 0
    found_solution = False
    TIMEOUT = 600

    start_time = time.perf_counter()

    try:
        for size in range(1, st.settings.max_literals + 1):

            if found_solution:
                break   # stop outer loop properly

            st.stats.update_num_literals(size)
            st.solver.update_number_of_literals(size)

            while True:

                # ---- TIMEOUT (global Popper timeout)
                if time.perf_counter() - start_time > TIMEOUT:
                    print(f"\n⏱️ TIMEOUT reached ({TIMEOUT}s)")
                    found_solution = True
                    break

                # ---- GENERATE
                with st.stats.duration('generate'):
                    model = st.solver.get_model()
                    if not model:
                        break

                    (program, before, min_clause) = generate_program(model)

                # ---- FEDERATED TEST
                start_fed = time.perf_counter()
                outcome, score, rules_str = federated_test(
                    program, store, nb_client, round_id
                )
                tFedPopper += time.perf_counter() - start_fed

                st.stats.total_programs += 1

                print(f"[Program #{round_id}] outcome={outcome}, score={score}")

                # ---- UPDATE BEST (independent from stopping)
                if best_score is None or score > best_score:
                    best_score = score
                    best_rules_str = list(rules_str)
                    best_round = round_id

                # ---- STOP CONDITION (true Popper semantics)
                if outcome == ("all", "none"):
                    print("\n Solution found (ALL, NONE)")
                    found_solution = True
                    break

                # ---- BUILD / GROUND / ADD
                start_symb = time.perf_counter()

                with st.stats.duration('build'):
                    rules = build_rules(
                        st.settings, st.stats, st.constrainer,
                        st.tester, program, before, min_clause, outcome
                    )

                with st.stats.duration('ground'):
                    rules = ground_rules(
                        st.stats, st.grounder,
                        st.solver.max_clauses, st.solver.max_vars, rules
                    )

                with st.stats.duration('add'):
                    st.solver.add_ground_clauses(rules)

                tCentralPopper += time.perf_counter() - start_symb

                round_id += 1

    finally:
        try:
            store.send(b"close")
            store.recv(1024)
        except:
            pass
        store.close()

    # ---- FINAL TIMING
    global_time = time.perf_counter() - start_time

    print("\n========== FINAL SUMMARY ==========")
    print(f"Total programs explored : {round_id}")
    print(f"Total execution time    : {global_time:.4f}s")

    if best_rules_str:
        print(f"\nBest hypothesis found at round {best_round} (score={best_score})")
        for r in best_rules_str:
            print(" ", r)
    else:
        print("No valid hypothesis found.")

    print("\n========== PERFORMANCE SUMMARY ==========")
    print(f"Total time           : {global_time:.4f}s")
    print(f"Time in Popper core  : {tCentralPopper:.4f}s")
    print(f"Time in Federation   : {tFedPopper:.4f}s")
    print(f"Coordination ratio   : {tFedPopper/global_time:.2%}")



# ================================
#   RUN
# ================================
if __name__ == "__main__":
    nb_client = 0
    run_server()