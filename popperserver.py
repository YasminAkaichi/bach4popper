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

import socket
import time
import numpy as np

STORE_HOST = "127.0.0.1"
STORE_PORT = 8000

LOG_EVERY = 50          # print 1 round sur 50
ASK_TIMEOUT_S = 120     # stop si on attend trop un client
BASE_SLEEP = 0.01       # polling initial
MAX_SLEEP = 0.2         # polling max

MAX_ROUNDS = 8000
PATIENCE = 500          # stop si pas d'amélioration pendant 500 rounds
STORE_SUPPORTS_BATCH = False  # mets True si le store supporte plusieurs commandes dans un seul sendall

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
def popper_initialisation(path_dir):
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



def tell_hypothesis25Jan(store, hyp, tour):
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
        



def get_epsilon_pairs(store, nb_client, tour):
    lepairs = []
    start = time.time()

    for i in range(1, nb_client + 1):
        sleep = BASE_SLEEP
        while True:
            if time.time() - start > ASK_TIMEOUT_S:
                raise TimeoutError(f"Timeout waiting epair for client {i} at round {tour}")

            msg = f"ask(epair({tour},{i}))"
            try:
                store.sendall(msg.encode("utf-8")[:1024])
                resp = store.recv(1024).decode("utf-8").strip()
            except socket.timeout:
                # pas de réponse → backoff
                time.sleep(sleep)
                sleep = min(MAX_SLEEP, sleep * 1.5)
                continue

            if ("wait" in resp) or ("failed" in resp) or (resp == ""):
                time.sleep(sleep)
                sleep = min(MAX_SLEEP, sleep * 1.5)
                continue

            lepairs.append(resp)
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
    cmd = f"tell(prgmlen({tour},0))"
    if STORE_SUPPORTS_BATCH:
        send_cmds_batch(store, [cmd])
    else:
        send_cmd(store, cmd)

def tell_hypothesis(store, hyp, tour):
    cmds = [f"tell(prgmlen({tour},{len(hyp)}))"]
    for i, clause in enumerate(hyp):
        payload = "{" + clause.strip() + "}"
        cmds.append(f"tell(prgm({tour},{i},{payload}))")

    if STORE_SUPPORTS_BATCH:
        send_cmds_batch(store, cmds)
    else:
        for c in cmds:
            send_cmd(store, c)


def make_store_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.settimeout(5.0)  # timeout sur recv pour éviter freeze complet
    s.connect((STORE_HOST, STORE_PORT))
    return s

def send_cmd(sock, cmd: str, ack_buf=1024):
    sock.sendall(cmd.encode())
    return sock.recv(ack_buf)

def send_cmds_batch(sock, cmds, ack_buf=1024):
    """
    Envoie plusieurs commandes en une fois puis lit N acks.
    Ne marche QUE si le STORE accepte plusieurs commandes concaténées.
    """
    payload = "\n".join(cmds) + "\n"
    sock.sendall(payload.encode())
    for _ in cmds:
        sock.recv(ack_buf)


# ================================
#   MAIN LOOP
# ================================

def run_server():
    cli_prompt()
    nb_client, path_dir = initialisation()
    st = popper_initialisation(path_dir)

    store = make_store_socket()
    print("Connected to STORE.")

    outcome_glob = None
    best_avg_score = float("-inf")
    best_rules_str = None
    best_round = None
    current_rules_str = []
    search_exhausted = False

    last_improve_round = 0

    try:
        round_id = 0
        while True:
            # ---- tell round ----
            send_cmd(store, f"tell(round({round_id}))")

            # ---- Round 0 bootstrap: empty hypothesis ----
            if round_id == 0 and outcome_glob is None:
                if round_id % LOG_EVERY == 0:
                    print(f"[ROUND {round_id}] bootstrap: send empty hypothesis")
                tell_empty_hypothesis(store, round_id)
                current_rules_str = []

            else:
                # ---- Popper step ----
                if round_id % LOG_EVERY == 0:
                    print(f"[ROUND {round_id}] outcome_glob={outcome_glob} best={best_avg_score:.4f}")

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

                raw_rules = rules_arr[0].tolist() if (rules_arr and len(rules_arr[0]) > 0) else []
                current_rules_str = [normalize_rule_for_store(r) for r in raw_rules]

                if raw_rules:
                    st.current_hypothesis = new_rules

                # publish hypothesis
                tell_hypothesis(store, current_rules_str, round_id)

            # ---- Read client feedback ----
            lepairs = get_epsilon_pairs(store, nb_client, round_id)
            parsed = [parse_epair_with_score(e) for e in lepairs]

            eps_pairs = [(ep, en) for (ep, en, _) in parsed]
            Eplus, Eminus = aggregate_outcomes(eps_pairs)
            outcome_glob = (Eplus, Eminus)

            scores = [s for (_, _, s) in parsed]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            # ---- Track best hypothesis ----
            if round_id != 0 and current_rules_str and avg_score > best_avg_score:
                best_avg_score = avg_score
                best_rules_str = list(current_rules_str)
                best_round = round_id
                last_improve_round = round_id
                if round_id % LOG_EVERY == 0:
                    print(f"  🏆 best updated @round {best_round} score={best_avg_score:.4f}")

            # ---- Stop: perfect solution ----
            if outcome_glob == ("all", "none"):
                print(f"✅ Global solution found at round {round_id}.")
                send_cmd(store, "close")
                break

            # ---- Stop: search exhausted ----
            if search_exhausted and outcome_glob != ("all", "none"):
                print("🛑 Search exhausted. Returning BEST hypothesis.")
                print(f"BEST round {best_round}, score={best_avg_score:.4f}")
                print("BEST hypothesis:", best_rules_str)
                send_cmd(store, "close")
                break

            # ---- Stop: max_literals reached ----
            if st.current_clause_size > st.settings.max_literals:
                print("🛑 max_literals reached. Returning BEST hypothesis.")
                print(f"BEST round {best_round}, score={best_avg_score:.4f}")
                print("BEST hypothesis:", best_rules_str)
                send_cmd(store, "close")
                break

            # ---- Stop: patience ----
            if round_id - last_improve_round >= PATIENCE and best_rules_str is not None:
                print("🛑 No improvement for PATIENCE rounds. Returning BEST hypothesis.")
                print(f"BEST round {best_round}, score={best_avg_score:.4f}")
                print("BEST hypothesis:", best_rules_str)
                send_cmd(store, "close")
                break

            # ---- Stop: max rounds ----
            if round_id >= MAX_ROUNDS:
                print("🛑 Max rounds reached. Returning BEST hypothesis.")
                print(f"BEST round {best_round}, score={best_avg_score:.4f}")
                print("BEST hypothesis:", best_rules_str)
                send_cmd(store, "close")
                break

            round_id += 1

    except Exception as e:
        print("Error:", e)

    finally:
        try:
            store.close()
        except:
            pass
        print("Connection to store closed.")

# ================================
#   RUN
# ================================
if __name__ == "__main__":
    nb_client = 0
    run_server()