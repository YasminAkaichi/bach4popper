import socket
from popper.util import Settings, Stats
from popper.asp import ClingoSolver, ClingoGrounder
from popper.constrain import Constrain
from popper.tester import Tester
from popper.core import Clause
from aggstrategy import aggregate_outcomes, aggregate_popper
import time
import numpy as np
from popper.structural_tester import StructuralTester

from popper.util import load_kbpath

NB_CLIENTS = 3
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/iggp-rps"
DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/zendo1"
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/trains"

#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/alzheimer"

import socket
from popper.util import Settings, Stats
from popper.asp import ClingoSolver, ClingoGrounder
from popper.constrain import Constrain
from popper.tester import Tester
from popper.core import Clause
from aggstrategy import aggregate_outcomes, aggregate_popper
import time
import numpy as np
from popper.structural_tester import StructuralTester

from popper.util import load_kbpath
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
        #self.nb_client = nb_client
        #self.path_dir = path_dir



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
    tester = StructuralTester()

    current_hypothesis = None
    current_before = None
    current_min_clause = 0
    current_clause_size = 0
    path_dir=path_dir
    #state = FILPServerState(settings, solver, grounder, constrainer, tester, stats, current_before,current_min_clause,current_clause_size,current_hypothesis)
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
    print("📤 Sending:", msg)
    store.send(msg.encode())
    store.recv(1024)

    for i, clause in enumerate(hyp):
        clean = clause.strip()
        # on suppose qu'il y a déjà un point final ou pas, comme tu veux
        payload = "{" + clean + "}"

        msg = f"tell(prgm({tour},{i},{payload}))"
        print("📤 Sending:", msg)
        store.send(msg.encode())
        store.recv(1024)


def tell_hypothesisWORKING(client,hyp, tour):
    nb_cl = len(hyp)
    str_nb_cl = str(nb_cl)
    msg = f"tell( prgmlen({tour},{str_nb_cl}) )"
    client.send(msg.encode("utf-8")[:1024])
    client.recv(1024)
    for i in range(0,nb_cl):
        print("in loop")
        str_i = str(i)
        clause = "{" + hyp[i] + "}"
        print(f"clause = {clause}")
        msg = f"tell( prgm({tour},{str_i},{clause}) )"
        client.send(msg.encode("utf-8")[:1024])
        client.recv(1024)


def tell_hypothesisold(client, hyp):
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



def parse_epairx(resp):
    # resp format: "epair(1,all,none)"
    parts = resp.strip().replace("epair(", "").replace(")", "").split(",")
    return parts[1], parts[2]   # (E+, E-)

def parse_epairx(s):
    if not s or "(" not in s or ")" not in s:
        return ("x", "x")   # default safe outcome
    s = s.strip()
    inner = s[s.find("(")+1 : s.rfind(")")]
    parts = [p.strip() for p in inner.split(",")]
    if len(parts) < 3:
        return ("x", "x ")
    return parts[1], parts[2]

def parse_epair(s):
    if not s or "(" not in s or ")" not in s:
        return ("none", "none")

    s = s.strip()
    inner = s[s.find("(")+1 : s.rfind(")")]
    parts = [p.strip().lower() for p in inner.split(",")]

    # Format attendu : epair(round, client, Eplus, Eminus)
    if len(parts) < 4:
        return ("none", "none")

    return parts[2], parts[3]


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

def normalize_rule_for_store_oold(rule_str):
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

def tell_empty_hypothesis(store, tour):
    msg = f"tell(prgmlen({tour},0))"
    print("📤 Sending:", msg)
    store.send(msg.encode())
    store.recv(1024)


def reset_store(store):
    print("Resetting STORE")
    store.send(b"reset")
    store.recv(1024)
# ================================
#   MAIN LOOP
# ================================
def stop_timer(start_time):
    end_time = time.time()
    return end_time, end_time - start_time



def run_server():
    cli_prompt()

    # --------------------------------------------------
    # 0) Initialisation
    # --------------------------------------------------
    nb_client, path_dir = initialisation()
    st = popper_initialisation(path_dir)

    store = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    store.connect(("127.0.0.1", 8000))
    print("Connected to STORE.")

    # Popper-style global feedback
    outcome_glob = (None, None)

    # Bookkeeping (equivalent to Stats)
    best_avg_score = float("-inf")
    best_rules_str = None
    best_round = None

    round_id = 0
    start_time = time.time()
    TIMEOUT = 600

    try:
        while True:
            elapsed = time.time() - start_time
            print("\n" + "=" * 50)
            print(f"[Popper] Program #{round_id}")
            print(f"[Time] Elapsed: {elapsed:.2f}s")
            print(f"[State] clause_size={st.current_clause_size}")
            print("=" * 50)

            # --------------------------------------------------
            # 1) ONE Popper step (federated)
            # --------------------------------------------------
            (
                rules_arr,
                min_clause,
                before,
                clause_size,
                solver,
                exhausted,
                new_hypothesis,
            ) = aggregate_popper(
                outcome_glob,
                st.settings,
                st.solver,
                st.grounder,
                st.constrainer,
                st.tester,
                st.stats,
                st.current_min_clause,
                st.current_before,
                st.current_hypothesis,
                st.current_clause_size,
            )

            # Update server state
            st.current_min_clause = min_clause
            st.current_before = before
            st.current_clause_size = clause_size
            st.solver = solver

            # --------------------------------------------------
            # 2) Stop if Popper search exhausted
            # --------------------------------------------------
            if exhausted:
                elapsed = time.time() - start_time
                print("\n🚫 SEARCH EXHAUSTED")
                print(f"Total programs tested: {round_id}")
                print(f"Total time: {elapsed:.2f}s")

                if best_rules_str:
                    print(
                        f"Best hypothesis found at program #{best_round} "
                        f"(avg_score={best_avg_score:.4f})"
                    )
                    for r in best_rules_str:
                        print("  ", r)
                else:
                    print("No valid hypothesis found.")

                break

            # --------------------------------------------------
            # 3) Publish round + hypothesis to STORE
            # --------------------------------------------------
            reset_store(store)

            store.send(f"tell(round({round_id}))".encode())
            store.recv(1024)

            raw_rules = rules_arr[0].tolist() if len(rules_arr[0]) > 0 else []
            current_rules_str = [normalize_rule_for_store(r) for r in raw_rules]

            print("[Published hypothesis]")
            if current_rules_str:
                for r in current_rules_str:
                    print("  ", r)
            else:
                print("  (empty hypothesis)")

            tell_hypothesis(store, current_rules_str, round_id)

            if raw_rules:
                st.current_hypothesis = new_hypothesis

            # --------------------------------------------------
            # 4) Collect client ε-pairs (+ scores)
            # --------------------------------------------------
            lepairs = get_epsilon_pairs(store, nb_client, round_id)
            parsed = [parse_epair_with_score(e) for e in lepairs]

            print("[Client feedback]")
            for p in parsed:
                print("  ", p)

            eps_pairs = [(ep, en) for (ep, en, _) in parsed]
            Eplus, Eminus = aggregate_outcomes(eps_pairs)
            outcome_glob = (Eplus, Eminus)

            print(f"[Aggregated outcome] {outcome_glob}")

            # --------------------------------------------------
            # 5) Score bookkeeping (best hypothesis)
            # --------------------------------------------------
            scores = [s for (_, _, s) in parsed]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            print(f"[Score] Avg score: {avg_score:.4f}")

            if raw_rules and avg_score > best_avg_score:
                best_avg_score = avg_score
                best_rules_str = list(current_rules_str)
                best_round = round_id
                print(
                    f" New BEST hypothesis at program #{best_round} "
                    f"(avg_score={best_avg_score:.4f})"
                )

            # --------------------------------------------------
            # 6) Stop if perfect solution (ALL/NONE)
            # --------------------------------------------------
            if outcome_glob == ("all", "none"):
                elapsed = time.time() - start_time
                print("\nGLOBAL SOLUTION FOUND")
                print(f"Program #{round_id}")
                print(f"Total time: {elapsed:.2f}s")

                for r in current_rules_str:
                    print("  ", r)

                reset_store(store)
                store.send(f"tell(final({round_id}))".encode())
                store.recv(1024)

                # 2) Publish FINAL hypothesis
                tell_hypothesis(store, current_rules_str, round_id)
                
                store.send(b"tell(done)")
                store.recv(1024)
                print("📤 Final hypothesis sent to clients.")

                break

            # --------------------------------------------------
            # 7) Global timeout (Popper-style safety)
            # --------------------------------------------------
            if time.time() - start_time > TIMEOUT:
                print(f"⏱️ TIMEOUT ({TIMEOUT}s) reached.")

                if best_rules_str:
                    print("📤 Sending FINAL hypothesis to clients")

                    reset_store(store)

                    store.send(f"tell(round({round_id}))".encode())
                    store.recv(1024)

                    tell_hypothesis(store, best_rules_str, round_id)

                    store.send(f"tell(final({round_id}))".encode())
                    store.recv(1024)

                break

            round_id += 1

    except Exception as e:
        print("❌ Server error:", e)

    finally:
        try:
            store.send(b"close")
            store.recv(1024)
        except Exception:
            pass

        store.close()

        elapsed = time.time() - start_time
        print("\n========== FINAL SUMMARY ==========")
        print(f"Total programs tested: {round_id}")
        print(f"Total execution time: {elapsed:.2f}s")

        if best_rules_str:
            print(
                f"Best hypothesis found at program #{best_round} "
                f"(avg_score={best_avg_score:.4f})"
            )
            for r in best_rules_str:
                print("  ", r)
        else:
            print("No valid hypothesis found.")

        print("Connection to STORE closed.")



# ================================
#   RUN
# ================================
if __name__ == "__main__":
    nb_client = 0
    run_server()