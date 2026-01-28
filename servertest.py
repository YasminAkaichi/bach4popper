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

from popper.loop import decide_outcome, calc_score
import traceback
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
    nb_client = int(input("- number of Popper clients: "))
    path_dir = input("- path to BK/Examples (folder): ")
    return nb_client,path_dir

# ================================
#   POPPER INITIALISE
# ================================
def popper_initialisation_old(path_dir):
    #global settings, stats, solver, grounder, constrainer, tester
    #global current_hypothesis, current_before, current_min_clause, current_clause_size
     
    print("Initialising Distributed FILP...")

    # Load bias file only
    # The user provides a path where: BK, EX, BIAS normally exist
    # Here we assume bias.pl is inside that folder
    #bias_file = f"{path_dir}/bias.pl"
    
    kbpath = f"{path_dir}"
    _, _, bias_file = load_kbpath(kbpath)
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


def popper_initialisation(path_dir):
    print("Initialising Distributed FILP...")

    # ========== FEDERATED / STRUCTURAL PART ==========
    kbpath = f"{path_dir}"
    _, _, bias_file = load_kbpath(kbpath)

    settings = Settings(bias_file, None, None)
    stats = Stats(log_best_programs=settings.info)
    solver = ClingoSolver(settings)
    grounder = ClingoGrounder()
    constrainer = Constrain()
    tester_structural = StructuralTester()

    # ========== CENTRALIZED TESTING PART ==========
    
    bk_file, ex_file, bias_file = load_kbpath(kbpath)
    settings_full = Settings(bias_file, ex_file, bk_file)
    tester_full = Tester(settings_full)

    state = FILPServerState(
        settings=settings,
        solver=solver,
        grounder=grounder,
        constrainer=constrainer,
        tester=tester_structural,
        stats=stats,
        min_clause=0,
        before=None,
        clause_size=0,
        hypothesis=None
    )

    # AJOUT IMPORTANT
    state.tester_full = tester_full

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


from popper.core import Clause, Literal
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

def central_test_hypothesis(hypothesis_strings, tester):
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

        #print(f"Total Pos examples: {len(tester.pos)}")
        #print(f"Total Neg examples: {len(tester.neg)}")

        cm = tester.test(rules)

        print("Confusion matrix:", cm)

        Eplus, Eminus = decide_outcome(cm)
        print(f"Outcome = ({Eplus}, {Eminus})")
        score = calc_score(cm)

        return str(Eplus).lower(), str(Eminus).lower(), float(score)

    except Exception as e:
        print("Error while testing hypothesis:")
        traceback.print_exc()
        return ("x", "x")




def run_server():
    cli_prompt()
    nb_client, path_dir = initialisation()
    st = popper_initialisation(path_dir)

    store = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    store.connect(("127.0.0.1", 8000))
    print("Connected to STORE.")

    # Global symbolic feedback from clients
    outcome_glob = None  # will become ("none","none") after round 0
    best_avg_score = float("-inf")
    best_rules_str = None
    best_round = None
    current_rules_str = []
    search_exhausted = False
    MAX_ROUNDS = 8000
    central_done = False
    central_round = None
    try:
        round_id = 0

        while True:


            print(f"\n========== ROUND {round_id} ==========")
            reset_store(store)
            #reset_msg = f"reset"
            #store.send(reset_msg.encode())
            #store.recv(1024)
            #reset_store(store)
            #print("fin reset")
            msg = f"tell(round({round_id}))"
            store.send(msg.encode())
            store.recv(1024)

            # --------------------------------------------------
            # ROUND 0: publish EMPTY program (no hypothesis)
            # Clients should respond with none/none and score=0
            # --------------------------------------------------
            if round_id == 0 and outcome_glob is None:
                print("Round 0: sending empty hypothesis (prgmlen=0) to bootstrap outcomes.")
                #reset_store(store)
                tell_empty_hypothesis(store, round_id)

            else:
                # ================================
                # 1) POPPER STEP (server-side)
                # ================================
                print("SERVER feeding outcome to Popper:", outcome_glob)

                rules_arr, current_min_clause, current_before, current_clause_size, solver, solved, new_rules = aggregate_popper(
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
                    st.current_clause_size
                )
                search_exhausted = solved
                st.current_min_clause = current_min_clause
                st.current_before = current_before
                st.current_clause_size = current_clause_size
                st.solver = solver

                # Update current hypothesis if non-empty
                #raw_rules = rules_arr[0].tolist() if (rules_arr and len(rules_arr[0]) > 0) else []
                #rules_str = [normalize_rule_for_store(r) for r in raw_rules]

                #if raw_rules:
                    #st.current_hypothesis = new_rules

                #print("Generated hypothesis:", rules_str)

                # Publish hypothesis to store
                #tell_hypothesis(store, rules_str, round_id)

                raw_rules = rules_arr[0].tolist() if (rules_arr and len(rules_arr[0]) > 0) else []
                current_rules_str = [normalize_rule_for_store(r) for r in raw_rules]

                if raw_rules:
                    st.current_hypothesis = new_rules

                print("Generated hypothesis:", current_rules_str)
                
                #reset_store(store)

                tell_hypothesis(store, current_rules_str, round_id)

                # ===============================================
                # CENTRALIZED TEST (REFERENCE)
                # ================================================
                Eplus_c, Eminus_c, score_c = central_test_hypothesis(current_rules_str,st.tester_full)

                print(f"[CENTRAL TEST] Outcome = ({Eplus_c}, {Eminus_c}), score = {score_c:.4f}")


                if not central_done and (Eplus_c, Eminus_c) == ("all", "none"):
                    central_done = True
                    central_round = round_id
                    print(f"[CENTRAL] Converged at round {round_id}")
                
                if central_done:
                    print(f"[CENTRAL] already converged (round {central_round})")

                # If solver exhausted (or solution found), we still read client feedback for bookkeeping,
                # but we may stop right after.
                if solved and outcome_glob != ("all", "none"):
                    print("Popper search exhausted (or stopping flag). Will fallback to best hypothesis after reading scores.")

            # ================================
            # 2) Read outcomes (+score) from clients
            # ================================
            lepairs = get_epsilon_pairs(store, nb_client, round_id)

            parsed = [parse_epair_with_score(e) for e in lepairs]
            print("PARSED outcomes+scores:", parsed)

            # Aggregate symbolic outcomes
            eps_pairs = [(ep, en) for (ep, en, _) in parsed]
            Eplus, Eminus = aggregate_outcomes(eps_pairs)
            outcome_glob = (Eplus, Eminus)
            print("AGGREGATED outcome:", outcome_glob)

            # Average score
            scores = [s for (_, _, s) in parsed]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            print(f"AVG score this round: {avg_score:.4f}")

            if round_id != 0 and current_rules_str and avg_score > best_avg_score:
                best_avg_score = avg_score
                best_rules_str = list(current_rules_str)
                best_round = round_id
                print(f"New BEST hypothesis at round {best_round} with avg_score={best_avg_score:.4f}")

            if search_exhausted and outcome_glob != ("all", "none"):
                print("Search exhausted. Returning BEST hypothesis.")
                if best_rules_str:
                    print(f"Best was round {best_round} with avg_score={best_avg_score:.4f} and best hypothesis {best_rules_str}")
                    #print("BEST hypothesis:", best_rules_str)
                else:
                    print("No best hypothesis found.")
                store.send(b"close")
                store.recv(1024)
                break

            # ================================
            # 3) Stop conditions
            # ================================
            # (A) Perfect global solution
            if outcome_glob == ("all", "none"):
                print("Global solution found (ALL/NONE). Stopping.")
                store.send(b"close")
                store.recv(1024)
                break

            # (B) Search exhausted: detect it via clause_size > max_literals
            #     We rely on the rule we added in aggregate_popper.
            if st.current_clause_size > st.settings.max_literals:
                print("Search exhausted (max_literals reached). Returning best hypothesis.")
                if best_rules_str:
                    print(f"Best was round {best_round} with avg_score={best_avg_score:.4f} and best hypothesis {best_rules_str}")
                    #print("BEST hypothesis:", best_rules_str)
                else:
                    print("No best hypothesis recorded (all rounds empty or scores missing).")

                store.send(b"close")
                store.recv(1024)
                break

            
            if round_id >= MAX_ROUNDS:
                #print("Max rounds reached. Returning BEST hypothesis.")
                print(f"Max rounds reached. Best was round {best_round} with avg_score={best_avg_score:.4f} and best hypothesis {best_rules_str}")
                #print(f"BEST round {best_round}, score={best_avg_score:.4f}")
                #print("BEST hypothesis:", best_rules_str)
                store.send(b"close")
                store.recv(1024)
                break

            round_id += 1

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