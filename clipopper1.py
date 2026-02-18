# clipopper.py
# ------------------------------------------------------
#   FILP Distributed Client using BLPy protocol
# ------------------------------------------------------

import socket
from popper.tester import Tester
from popper.core import Literal
from popper.loop import decide_outcome, calc_score
from popper.util import Settings, Stats
from popper.util import load_kbpath
import re
import traceback

CLIENT_ID = 1 

#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/iggp-rps_part1"
DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/zendo1_part1"
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/trains_part1"
#DATASET_PATH = "/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/datasets/alzheimer_p1"
# ======================================================
#  BLPy parsing helpers
# ======================================================

def get_nb_clause_from_prgmlen_si(ast):
    try:
        arg_prgmlen_si = ast.arguments
        nb_cl = arg_prgmlen_si[0]
        return nb_cl
    except Exception as e:
        print(f"Error: {e}")

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
    client_id = int(CLIENT_ID)
    path_dir = DATASET_PATH
    
    #LOAD PROLOG BACKGROUND + EXAMPLES
    bk, ex, bias = load_kbpath(path_dir)
    settings = Settings(bias, ex, bk)
    tester = Tester(settings)
    stats = Stats(log_best_programs=settings.info)
    settings.num_pos, settings.num_neg = len(tester.pos), len(tester.neg)
    # 🔎 DEBUG: compare FILE vs TESTER
    file_pos, file_neg = count_pos_neg_in_file(ex)
    print(f"[CLIENT {client_id}] FILE counts   pos={file_pos} neg={file_neg}")
    print(f"[CLIENT {client_id}] TESTER counts pos={len(tester.pos)} neg={len(tester.neg)}")
    return client_id, path_dir, settings, tester, stats



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



def send_epair(sock, client_id, tour, Eplus, Eminus, score):
    score_int = int(float(score)) 
    msg = f"tell(epair({tour},{client_id},{Eplus},{Eminus},{score_int}))"
    sock.send(msg.encode())
    sock.recv(1024)  # confirmation du store


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

            # FINAL
            if nb_raw == "final":
                print("\n FINAL round detected")
                print("Final hypothesis:")
                for h in hypothesis:
                    print("  ", h)
                break

            # NORMAL
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




if __name__ == "__main__":
    run_client()