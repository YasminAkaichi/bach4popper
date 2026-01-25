import socket
import re
from popper.util import Settings, Stats, load_kbpath
from popper.tester import Tester
from popper.loop import decide_outcome
from popper.core import Literal


# ======================================================
#  Lire l'hypothèse depuis le STORE
# ======================================================
def popper_read_hypothesis(sock):
    """Lit l'hypothèse courante dans le STORE comme liste de règles Popper."""

    # 1️⃣ demander la longueur de l'hypothèse
    msg = "ask( prgmlen )"
    sock.send(msg.encode("utf-8")[:1024])
    resp = sock.recv(1024).decode("utf-8").strip()
    print("📥 prgmlen →", resp)

    m = re.search(r"prgmlen\((\d+)\)", resp)
    if not m:
        print("❌ Impossible d'extraire prgmlen, on renvoie []")
        return []
    number_of_clauses = int(m.group(1))
    print(f"➡️ Nombre de clauses dans l'hypothèse : {number_of_clauses}")

    clauses = []

    # 2️⃣ récupérer chaque clause séparément
    for clause_index in range(number_of_clauses):
        msg = f"ask( prgm({clause_index}) )"
        sock.send(msg.encode("utf-8")[:1024])
        resp = sock.recv(4096).decode("utf-8").strip()
        print(f"📥 prgm({clause_index}) →", resp)

        # extraire { ... }
        m = re.search(r"\{(.*)\}", resp)
        if not m:
            print(f"❌ Pas de corps de règle trouvé pour l'index {clause_index}")
            continue

        rule = m.group(1).strip()

        # normalisation Popper minimale
        rule = rule.replace(" ", "")
        rule = rule.replace(";", ",")
        if not rule.endswith("."):
            rule += "."

        print("   ✓ règle parsée pour Popper :", rule)
        clauses.append(rule)

    return clauses


# ======================================================
#  Tester l'hypothèse localement avec Popper
# ======================================================
def popper_test_local(rule_strings, tester):
    """Retourne (Eplus, Eminus) à partir d'une liste de strings de règles."""
    if not rule_strings:
        return ("none", "none")

    try:
        rules = []
        for r in rule_strings:
            r = r.strip()
            if r.endswith("."):
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

        return (Eplus.name.lower(), Eminus.name.lower())

    except Exception as e:
        print("🔥 Échec du test local Popper :", e)
        return ("none", "none")


# ======================================================
#  Reporter epair au STORE
# ======================================================
def popper_report_epair(sock, client_id, Eplus, Eminus):
    msg = f"tell( epair({client_id},{Eplus},{Eminus}) )"
    print("📤 epair envoyé →", msg)
    sock.send(msg.encode("utf-8")[:1024])
    _ = sock.recv(1024)  # ACK du store


# ======================================================
#  Option pour interagir à la main (comme ton code simple)
# ======================================================
def check_finish():
    endi = input("Indicate if finish (0 = no, 1 = yes): ")
    return (endi == "1")


# ======================================================
#  MAIN CLIENT
# ======================================================
def run_client():
    # connexion au STORE
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_ip = "127.0.0.1"
    server_port = 8000
    sock.connect((server_ip, server_port))

    print("""
 __ .   .__                
/  `|*  [__) _ ._ ._  _ ._.
\__.||  |   (_)[_)[_)(/,[  
               |  |        
""")

    print("Please introduce ... ")
    client_id = input("- the number to identify the client: ")
    path_dir = input("- the path to example files (BK/EX/BIAS): ")

    # Initialisation Popper locale
    bk, ex, bias = load_kbpath(path_dir)
    settings = Settings(bias, ex, bk)
    tester = Tester(settings)
    settings.num_pos, settings.num_neg = len(tester.pos), len(tester.neg)
    Stats(log_best_programs=settings.info)

    finish_learning = False

    try:
        while not finish_learning:
            # 1) lire hypothèse depuis le STORE
            hypothesis = popper_read_hypothesis(sock)
            print("📌 Hypothesis reçue :", hypothesis)

            # 2) tester localement
            Eplus, Eminus = popper_test_local(hypothesis, tester)
            print(f"📊 Outcome local = ({Eplus}, {Eminus})")

            # 3) envoyer epair au STORE
            popper_report_epair(sock, client_id, Eplus, Eminus)

            # 4) stopper ou pas (comme dans le code original)
            finish_learning = check_finish()

    except Exception as e:
        print("❌ Erreur client :", e)

    finally:
        sock.close()
        print("Connection to server closed")


if __name__ == "__main__":
    run_client()
