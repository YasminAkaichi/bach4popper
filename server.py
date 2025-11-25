import socket
from popper.util import Settings, Stats
from popper.asp import ClingoSolver, ClingoGrounder
from popper.constrain import Constrain
from popper.tester import Tester
from popper.core import Clause
from aggstrategy import aggregate_outcomes, aggregate_popper


# ================================
#    GLOBAL STATE
# ================================
settings = None
stats = None
solver = None
grounder = None
constrainer = None
tester = None

current_hypothesis = None
current_before = None
current_min_clause = None
current_clause_size = 1


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
    global nb_client
    global path_dir
    print("Please introduce ...")
    nb_client = int(input("- number of Popper clients: "))
    path_dir = input("- path to BK/Examples (folder): ")


# ================================
#   POPPER INITIALISE
# ================================
def popper_initialisation():
    global settings, stats, solver, grounder, constrainer, tester
    global current_hypothesis, current_before, current_min_clause, current_clause_size

    print("Initialising Distributed FILP...")

    # Load bias file only
    # The user provides a path where: BK, EX, BIAS normally exist
    # Here we assume bias.pl is inside that folder
    bias_file = f"{path_dir}/bias.pl"

    settings = Settings(bias_file, None, None)
    stats = Stats(log_best_programs=settings.info)
    solver = ClingoSolver(settings)
    grounder = ClingoGrounder()
    constrainer = Constrain()
    tester = Tester(settings)

    current_hypothesis = None
    current_before = None
    current_min_clause = None
    current_clause_size = 1


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
    global nb_client
    lepairs = []
    str_nb_client = str(nb_client)
    print(f"nb_client = {str_nb_client}")
    for i in range(1,nb_client+1):
        str_i = str(i)
        msg = f"ask( epair({str_i}) )"
        client.send(msg.encode("utf-8")[:1024])
        response = client.recv(1024)
        response = response.decode("utf-8")        
        lepairs.append(response)
    # msg = "reset"
    # client.send(msg.encode("utf-8")[:1024])
    # client.recv(1024)
    return lepairs



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
# ================================
#   MAIN LOOP
# ================================

def run_server():

    global current_hypothesis, current_before, current_min_clause, current_clause_size, solver

    # SETTINGS OK
    
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_ip = "127.0.0.1"  # replace with the server's IP address
    server_port = 8000  # replace with the server's port number
    client.connect((server_ip, server_port))

    finish_learning = False
    hypothesis = []
     
    try:               
        cli_prompt()
        initialisation()
        popper_initialisation()  
        while not finish_learning:  
            if (Eplus, Eminus) == ("all","none"):
                break
            # 1) POPPER: génération initiale
            rules_arr, current_min_clause, current_before, current_clause_size, solver, solved = aggregate_popper(
            None,
            settings,
            solver,
            grounder,
            constrainer,
            tester,
            stats,
            current_min_clause,
            current_before,
            current_hypothesis,
            current_clause_size,)
        
            # Convertir en Clause et strings
            current_hypothesis = [Clause.from_string(r) for r in rules_arr[0].tolist()]
            #rules_str = [Clause.to_code(r) for r in current_hypothesis]
            rules_str = []

            for r in current_hypothesis:
                s = Clause.to_code(r)

                # s = 'f(A):-has_car(A),three_wheels(B)'

                # 1) remettre les virgules
                s = s.replace(";", ",")

                # 2) ajouter un point s'il n'y en a pas
                if not s.endswith("."):
                    s += "."

                rules_str.append(s)

            


            print(f"current hypo = ({current_hypothesis})")

            print(f"rules_str = ({rules_str})")
            tell_hypothesis(client, rules_str)

            # 3) RECEVOIR TOUS LES EPAIRS
            all_pairs = []

            lepairs = get_epsilon_pairs(client)
            parsed = [parse_epair(e) for e in lepairs]
            all_pairs.extend(parsed)

            Eplus, Eminus = aggregate_outcomes(all_pairs)
            print(f"Aggregated outcome = ({Eplus}, {Eminus})")

            # 4) POPPER maj contraintes et re-génération
            rules_arr, current_min_clause, current_before, current_clause_size, solver, solved = aggregate_popper(
                (Eplus, Eminus),
                settings,
                solver,
                grounder,
                constrainer,
                tester,
                stats,
                current_min_clause,
                current_before,
                current_hypothesis,
                current_clause_size,
            )

            current_hypothesis = [Clause.from_string(r) for r in rules_arr[0].tolist()]

            # Stop
            if (Eplus, Eminus) == ("all", "none"):
                print("Global solution reached. Stopping.")
                finished = True
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # close client socket (connection to the server)
        client.close()
        print("Connection to server closed")


# ================================
#   RUN
# ================================
if __name__ == "__main__":
    nb_client = 0
    run_server()
