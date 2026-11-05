# srvpopper.py
# ------------------------------------------------------
#   FILP Distributed Server using BLPy protocol
# ------------------------------------------------------

import json
import os
import re
import socket
import time

from popper.asp import ClingoSolver, ClingoGrounder
from popper.constrain import Constrain
from popper.core import Clause
from popper.federatedtester import FederatedTester
from popper.util import load_kbpath, Settings, Stats
from popper.loop import build_rules_server, ground_rules
from popper.generate import generate_program

from .strategy.aggstrategy import aggregate_outcomes

# ======================================================
#  SERVER CONFIGURATION
# ======================================================

import argparse


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        BASE_DIR,
        "..",
    )
)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the Bach4Popper coordination server."
    )

    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to the global dataset directory.",
    )

    parser.add_argument(
        "--clients",
        type=int,
        required=True,
        help="Number of expected coordination clients.",
    )

    parser.add_argument(
        "--rounds",
        type=int,
        default=35000,
        help=(
            "Unused — the main loop below never checks this value "
            "against round_id, so it was never a real stopping "
            "condition. Kept only for CLI/launcher backward "
            "compatibility. The real stopping conditions are: an exact "
            "solution found, --timeout reached, or the search space "
            "exhausted."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help=(
            "Seconds the Popper search is allowed to run before it "
            "stops and returns the best hypothesis found so far, if no "
            "exact solution has been found yet."
        ),
    )

    parser.add_argument(
        "--store-address",
        type=str,
        default="127.0.0.1:8000",
        help="Bach coordination store address.",
    )

    parser.add_argument(
        "--timing-mode",
        type=str,
        choices=["wall", "cpu"],
        default="wall",
        help=(
            "'wall' (default) times with time.perf_counter(), including "
            "time spent blocked waiting on clients — comparable to the "
            "Collaboration server and to client-side eval times. 'cpu' "
            "times with time.process_time(), excluding waiting, which "
            "makes learning_time/popper_time/federation_time NOT "
            "comparable to wall-clock client evaluation time."
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=(
            "Directory to write server_result.json into (same schema as "
            "the Collaboration server), so the launcher can persist "
            "results to the database. If omitted, no file is written."
        ),
    )

    return parser.parse_args()


def resolve_dataset_path(
    dataset_argument: str,
) -> str:
    if os.path.isabs(dataset_argument):
        dataset_path = dataset_argument
    else:
        dataset_path = os.path.join(
            PROJECT_ROOT,
            dataset_argument,
        )

    dataset_path = os.path.abspath(
        dataset_path
    )

    if not os.path.isdir(dataset_path):
        raise FileNotFoundError(
            f"Server dataset directory not found: {dataset_path}"
        )

    return dataset_path


def parse_address(
    address: str,
) -> tuple[str, int]:
    host, port = address.rsplit(
        ":",
        1,
    )

    return host, int(port)
# ======================================================
#  GLOBAL STATE
# ======================================================

class FILPServerState:
    """
    Preserve the complete Popper solver state
    between federated rounds.
    """

    def __init__(
        self,
        settings,
        solver,
        grounder,
        constrainer,
        tester,
        stats,
        min_clause,
        before,
        clause_size,
        hypothesis,
    ):
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


# ======================================================
#  UI
# ======================================================

def cli_prompt():

    banner = r"""
   _____               ____
  / ___/______   __   / __ \____  ____  ____  ___  _____
  \__ \/ ___/ | / /  / /_/ / __ \/ __ \/ __ \/ _ \/ ___/
 ___/ / /   | |/ /  / ____/ /_/ / /_/ / /_/ /  __/ /
/____/_/    |___/  /_/    \____/ .___/ .___/\___/_/
                               /_/   /_/
"""

    print(banner)


# ======================================================
#  INITIALISATION
# ======================================================


def popper_initialisation(path_dir):

    print(
        "Initialising Distributed FILP..."
    )

    # Server loads only the bias.
    _, _, bias_file = load_kbpath(
        path_dir
    )

    settings = Settings(
        bias_file,
        None,
        None,
        eval_timeout=float(os.environ.get("FILP_EVAL_TIMEOUT", "0.1")),
    )

    stats = Stats(
        log_best_programs=settings.info
    )

    solver = ClingoSolver(
        settings
    )

    grounder = ClingoGrounder()

    constrainer = Constrain()

    tester = FederatedTester(
        settings
    )

    current_hypothesis = None
    current_before = None
    current_min_clause = 0
    current_clause_size = 0

    state = FILPServerState(
        settings=settings,
        solver=solver,
        grounder=grounder,
        constrainer=constrainer,
        tester=tester,
        stats=stats,
        min_clause=current_min_clause,
        before=current_before,
        clause_size=current_clause_size,
        hypothesis=current_hypothesis,
    )

    return state


# ======================================================
#  STORE HELPERS
# ======================================================

def reset_store(store):

    print("Resetting STORE")

    store.send(
        b"reset"
    )

    store.recv(
        1024
    )


def normalize_rule_for_store(
    rule_str,
):
    """
    Transform a Popper rule into a clean representation
    suitable for the coordination store.
    """

    rule = (
        rule_str
        .replace("{", "")
        .replace("}", "")
        .strip()
    )

    if rule.endswith("."):
        rule = rule[:-1]

    rule = rule.replace(
        ";",
        ",",
    )

    if ":-" in rule:

        head, body = rule.split(
            ":-",
            1,
        )

        rule = (
            f"{head.strip()} :- "
            f"{body.strip()}"
        )

    else:
        rule = rule.strip()

    if not rule.endswith("."):
        rule += "."

    return rule


# ======================================================
#  SEND HYPOTHESIS TO CLIENTS
# ======================================================

def tell_hypothesis(
    store,
    hypothesis,
    tour,
):

    number_of_clauses = len(
        hypothesis
    )

    # --------------------------------------------------
    # Number of clauses
    # --------------------------------------------------

    message = (
        f"tell(prgmlen("
        f"{tour},"
        f"{number_of_clauses}"
        f"))"
    )

    print(
        "Sending:",
        message,
    )

    store.send(
        message.encode()
    )

    store.recv(
        1024
    )

    # --------------------------------------------------
    # Clauses
    # --------------------------------------------------

    for clause_index, clause in enumerate(
        hypothesis
    ):

        clean_clause = clause.strip()

        payload = (
            "{"
            + clean_clause
            + "}"
        )

        message = (
            f"tell(prgm("
            f"{tour},"
            f"{clause_index},"
            f"{payload}"
            f"))"
        )

        print(
            "Sending:",
            message,
        )

        store.send(
            message.encode()
        )

        store.recv(
            1024
        )


# ======================================================
#  EPSILON FEEDBACK
# ======================================================

def get_epsilon_pairs(
    store,
    nb_client,
    tour,
    first_client=1,
):

    epsilon_pairs = []

    print(
        f"nb_client = {nb_client}"
    )

    for client_id in range(
        first_client,
        nb_client + 1,
    ):

        while True:

            message = (
                f"ask(epair("
                f"{tour},"
                f"{client_id}"
                f"))"
            )

            store.send(
                message.encode("utf-8")[:1024]
            )

            response = (
                store.recv(1024)
                .decode("utf-8")
                .strip()
            )

            print(
                "Response from store:",
                response,
            )

            if (
                "wait" in response
                or "failed" in response
            ):
                time.sleep(
                    0.05
                )

                continue

            epsilon_pairs.append(
                response
            )

            break

    return epsilon_pairs


def parse_epair_with_score(
    response,
):
    """
    Expected:

        epair(
            round,
            client,
            Eplus,
            Eminus,
            score
        )
    """

    if (
        not response
        or "(" not in response
        or ")" not in response
    ):
        return (
            "none",
            "none",
            0.0,
        )

    inner = response[
        response.find("(") + 1:
        response.rfind(")")
    ]

    parts = [
        part.strip().lower()
        for part in inner.split(",")
    ]

    if len(parts) >= 5:

        epsilon_positive = parts[2]
        epsilon_negative = parts[3]

        try:
            score = float(
                parts[4]
            )

        except Exception:
            score = 0.0

        return (
            epsilon_positive,
            epsilon_negative,
            score,
        )

    # Backward compatibility
    if len(parts) >= 4:

        return (
            parts[2],
            parts[3],
            0.0,
        )

    return (
        "none",
        "none",
        0.0,
    )


# ======================================================
#  CLAUSE-LEVEL FEEDBACK
# ======================================================

def parse_rule_feedback(
    response,
):
    """
    Expected:

        rulefb(
            round,
            client,
            clause_index,
            inconsistent,
            totally_incomplete
        )

    Returns:

        inconsistent: bool
        totally_incomplete: bool
    """

    if (
        not response
        or "(" not in response
        or ")" not in response
    ):
        raise ValueError(
            f"Invalid rule feedback: {response}"
        )

    inner = response[
        response.find("(") + 1:
        response.rfind(")")
    ]

    parts = [
        part.strip()
        for part in inner.split(",")
    ]

    if len(parts) < 5:
        raise ValueError(
            f"Invalid rule feedback: {response}"
        )

    inconsistent = bool(
        int(parts[3])
    )

    totally_incomplete = bool(
        int(parts[4])
    )

    return (
        inconsistent,
        totally_incomplete,
    )


def get_rule_feedback(
    store,
    nb_client,
    tour,
    number_of_clauses,
    first_client=1,
):
    """
    Retrieve clause-level feedback from all clients.

    Flower-equivalent aggregation:

        inconsistent(rule)
            = ANY client says inconsistent

        totally_incomplete(rule)
            = ALL clients say totally incomplete
    """

    # --------------------------------------------------
    # Feedback matrix:
    #
    # client -> [feedback clause 0, clause 1, ...]
    # --------------------------------------------------

    all_inconsistent_rules = []
    all_totally_incomplete_rules = []

    for client_id in range(
        first_client,
        nb_client + 1,
    ):

        client_inconsistent_rules = []
        client_totally_incomplete_rules = []

        for clause_index in range(
            number_of_clauses
        ):

            while True:

                message = (
                    f"ask(rulefb("
                    f"{tour},"
                    f"{client_id},"
                    f"{clause_index}"
                    f"))"
                )

                store.send(
                    message.encode("utf-8")[:1024]
                )

                response = (
                    store.recv(1024)
                    .decode("utf-8")
                    .strip()
                )

                print(
                    "Rule feedback from store:",
                    response,
                )

                if (
                    "wait" in response
                    or "failed" in response
                ):

                    time.sleep(
                        0.05
                    )

                    continue

                (
                    is_inconsistent,
                    is_totally_incomplete,
                ) = parse_rule_feedback(
                    response
                )

                client_inconsistent_rules.append(
                    is_inconsistent
                )

                client_totally_incomplete_rules.append(
                    is_totally_incomplete
                )

                break

        all_inconsistent_rules.append(
            client_inconsistent_rules
        )

        all_totally_incomplete_rules.append(
            client_totally_incomplete_rules
        )

    # --------------------------------------------------
    # Flower-equivalent aggregation
    # --------------------------------------------------

    if number_of_clauses == 0:

        return (
            [],
            [],
        )

    aggregated_inconsistent_rules = [
        any(client_feedback)
        for client_feedback in zip(
            *all_inconsistent_rules
        )
    ]

    aggregated_totally_incomplete_rules = [
        all(client_feedback)
        for client_feedback in zip(
            *all_totally_incomplete_rules
        )
    ]

    print(
        "[SERVER] Aggregated inconsistent rules:",
        aggregated_inconsistent_rules,
    )

    print(
        "[SERVER] Aggregated totally incomplete rules:",
        aggregated_totally_incomplete_rules,
    )

    return (
        aggregated_inconsistent_rules,
        aggregated_totally_incomplete_rules,
    )

def finalize_with_best_hypothesis(
    store,
    best_program,
    nb_client,
    round_id,
):
    """
    Same principle as the Collaboration side's
    _send_best_hypothesis_for_final_validation(): when the search stops
    without an exact solution (timeout or exhausted search space), each
    client's own client_<id>_result.json would otherwise reflect
    whatever hypothesis it last happened to test — not necessarily
    best_program, since an earlier round can have scored higher than
    the most recent one. Worse, before this fix, tell_final_hypothesis()
    was never even called in the timeout/exhausted case, so clients
    never learned the search had ended.

    Re-running federated_test() on best_program one more time — a
    genuine extra round, going through the exact same code path every
    other hypothesis goes through — means every client actually tests
    and reports on the hypothesis that ends up reported as the final
    answer. tell_final_hypothesis() is then sent so clients stop
    cleanly instead of blocking on a round that will never come.

    Returns (rules_str, next_round_id). rules_str is None if there was
    no best_program to validate (nothing was ever found).
    """
    if not best_program:
        return None, round_id

    print(
        "\nSending best hypothesis to all clients for final "
        "validation before stopping..."
    )

    (
        outcome,
        score,
        rules_str,
        _inconsistent_rules,
        _totally_incomplete_rules,
    ) = federated_test(
        program=best_program,
        store=store,
        nb_client=nb_client,
        round_id=round_id,
    )

    print(
        f"[Final validation] outcome={outcome}, score={score}"
    )

    final_round = round_id + 1

    tell_final_hypothesis(
        store=store,
        hypothesis=rules_str,
        tour=final_round,
    )

    return rules_str, round_id + 1


def tell_final_hypothesis(
    store,
    hypothesis,
    tour,
):
    print(
        f"[SERVER] Publishing final hypothesis at round {tour}"
    )

    # Mark round as final
    message = (
        f"tell(prgmlen("
        f"{tour},"
        f"final"
        f"))"
    )

    print("Sending:", message)

    store.send(
        message.encode()
    )

    store.recv(
        1024
    )

    # Publish every final clause
    for clause_index, clause in enumerate(
        hypothesis
    ):
        clean_clause = clause.strip()

        payload = (
            "{"
            + clean_clause
            + "}"
        )

        message = (
            f"tell(prgm("
            f"{tour},"
            f"{clause_index},"
            f"{payload}"
            f"))"
        )

        print("Sending:", message)

        store.send(
            message.encode()
        )

        store.recv(
            1024
        )

# ======================================================
#  FEDERATED TEST
# ======================================================

# What each client answered for the program tested last (filled by
# federated_test, read by the main loop to build hypothesis_log.json).
LAST_CLIENT_OUTCOMES: list = []


def federated_test(
    program,
    store,
    nb_client,
    round_id,
):
    """
    Distributed equivalent of tester.test(program).

    The server:

        1. sends the hypothesis;
        2. receives epsilon+/epsilon-/score;
        3. receives clause-level Popper feedback;
        4. aggregates everything exactly as in FedPopper.
    """

    # --------------------------------------------------
    # Program -> strings
    # --------------------------------------------------

    rules_str = [
        normalize_rule_for_store(
            Clause.to_code(clause)
        )
        for clause in program
    ]

    # --------------------------------------------------
    # Publish hypothesis
    # --------------------------------------------------

    reset_store(
        store
    )

    store.send(
        f"tell(round({round_id}))".encode()
    )

    store.recv(
        1024
    )

    tell_hypothesis(
        store=store,
        hypothesis=rules_str,
        tour=round_id,
    )

    # --------------------------------------------------
    # Retrieve epsilon feedback
    # --------------------------------------------------

    epsilon_pairs = get_epsilon_pairs(
        store=store,
        nb_client=nb_client,
        tour=round_id,
    )

    parsed_epsilon_pairs = [
        parse_epair_with_score(
            epsilon_pair
        )
        for epsilon_pair in epsilon_pairs
    ]

    LAST_CLIENT_OUTCOMES.clear()
    for client_number, (pos, neg, client_score) in enumerate(
        parsed_epsilon_pairs, start=1
    ):
        LAST_CLIENT_OUTCOMES.append(
            {
                "client": client_number,
                "epsilon_positive": str(pos),
                "epsilon_negative": str(neg),
                "score": float(client_score),
            }
        )

    # --------------------------------------------------
    # Aggregate ALL / SOME / NONE
    # --------------------------------------------------

    outcomes = [
        (
            epsilon_positive,
            epsilon_negative,
        )
        for (
            epsilon_positive,
            epsilon_negative,
            _
        ) in parsed_epsilon_pairs
    ]

    outcome = aggregate_outcomes(
        outcomes
    )

    # --------------------------------------------------
    # Aggregate score
    # --------------------------------------------------

    scores = [
        score
        for (
            _,
            _,
            score
        ) in parsed_epsilon_pairs
    ]

    fed_score = sum(
        scores
    )

    # --------------------------------------------------
    # Retrieve and aggregate clause feedback
    # --------------------------------------------------

    (
        inconsistent_rules,
        totally_incomplete_rules,
    ) = get_rule_feedback(
        store=store,
        nb_client=nb_client,
        tour=round_id,
        number_of_clauses=len(program),
    )

    print(
        f"[SERVER] Global outcome = {outcome}"
    )

    print(
        f"[SERVER] Global score = {fed_score}"
    )

    return (
        outcome,
        fed_score,
        rules_str,
        inconsistent_rules,
        totally_incomplete_rules,
    )


# ======================================================
#  MAIN LOOP
# ======================================================

def run_server(
    with_suspension=None,
):
    tFedPopper = 0.0
    tCentralPopper = 0.0
    args = parse_arguments()

    # CLI --timing-mode is the actual source of truth (mirrors
    # engines/collaboration/server.py's with_suspension=(args.timing_mode
    # == "wall")); the function parameter is only a fallback for direct
    # callers that don't go through argparse.
    if with_suspension is None:
        with_suspension = args.timing_mode == "wall"

    if args.clients < 1:
        raise ValueError(
            "The number of clients must be at least 1."
        )

    nb_client = int(
        args.clients
    )

    path_dir = resolve_dataset_path(
        args.dataset
    )

    store_address = parse_address(
        args.store_address
    )

    print(
        "========== BACH4POPPER SERVER =========="
    )

    print(
        f"Dataset       : {path_dir}"
    )

    print(
        f"Clients       : {nb_client}"
    )

    print(
        f"Max rounds    : {args.rounds}"
    )

    print(
        f"Store address : {args.store_address}"
    )

    st = popper_initialisation(
        path_dir
    )

    store = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    # Mirrors "startup_time" on the Collaboration side: everything before
    # the learning loop actually starts (here, just the socket connect —
    # there's no client-sampling wait since Bach clients connect to the
    # store independently, not to this server).
    connect_start = time.perf_counter()

    store.connect(
        store_address
    )

    startup_time = time.perf_counter() - connect_start

    print(
        "Connected to STORE."
    )

    # --------------------------------------------------
    # Best hypothesis tracking
    # --------------------------------------------------

    best_score = None
    best_rules_str = None
    best_program = None

    # One entry per program tested (same format as the Collaboration side),
    # saved to hypothesis_log.json: lets two searches be compared round by round.
    hypothesis_log = []
    best_round = None

    round_id = 0
    found_solution = False

    # Distinct from found_solution: found_solution just means "the
    # search loop is done" (true for TIMEOUT and exhausted-search too,
    # where best_rules_str is only an approximate best-effort guess).
    # exact_solution_found is true ONLY when a rule was found that
    # perfectly separates the examples (outcome == ("all", "none")).
    # Without this distinction, solution_found in the saved result —
    # and therefore "Completed"/acceptance badges in the UI — was
    # wrongly True any time best_rules_str existed at all, even for a
    # best-effort hypothesis returned after a timeout or exhausted
    # search that no client actually accepted locally.
    exact_solution_found = False

    # Was hardcoded to 600 regardless of what the user configured — now
    # driven by --timeout, matching the Collaboration/Flower side.
    TIMEOUT = args.timeout

    # --------------------------------------------------
    # Timer selection
    # --------------------------------------------------

    timer = (
        time.perf_counter
        if with_suspension
        else time.process_time
    )

    # Timeout always uses wall-clock time.
    wall_start = time.perf_counter()

    start_time = timer()

    try:

        for size in range(
            1,
            st.settings.max_literals + 1,
        ):

            if found_solution:
                break

            st.stats.update_num_literals(
                size
            )

            st.solver.update_number_of_literals(
                size
            )

            while True:

                # ------------------------------------------
                # TIMEOUT
                # ------------------------------------------

                # A STOP requested from the UI ("Stop" button, see
                # core/run_control.py) is handled exactly like a timeout:
                # stop searching, validate the best hypothesis so far.
                stop_requested = bool(args.output_dir) and os.path.exists(
                    os.path.join(args.output_dir, "STOP")
                )

                if (
                    time.perf_counter()
                    - wall_start
                    > TIMEOUT
                ) or stop_requested:

                    print(
                        "\nSTOP requested by the user"
                        if stop_requested
                        else f"\nTIMEOUT reached ({TIMEOUT}s)"
                    )

                    (
                        validated_rules_str,
                        round_id,
                    ) = finalize_with_best_hypothesis(
                        store=store,
                        best_program=best_program,
                        nb_client=nb_client,
                        round_id=round_id,
                    )

                    if validated_rules_str is not None:
                        best_rules_str = validated_rules_str

                    found_solution = True

                    break

                # ------------------------------------------
                # GENERATE
                # ------------------------------------------

                # The GENERATE step (the ASP solver proposing the next
                # program) is part of the server's own Popper work, like
                # build / ground / add below. It used to be timed only in
                # st.stats and never added to tCentralPopper, so it showed
                # up as "not measured" time (large when the search space
                # is big: the solver is then the bottleneck).
                start_generate = timer()

                try:

                    with st.stats.duration(
                        "generate"
                    ):

                        model = (
                            st.solver.get_model()
                        )

                        if not model:
                            break

                        (
                            program,
                            before,
                            min_clause,
                        ) = generate_program(
                            model
                        )

                finally:

                    tCentralPopper += (
                        timer()
                        - start_generate
                    )

                # ------------------------------------------
                # FEDERATED TEST
                # ------------------------------------------

                start_fed = timer()

                with st.stats.duration(
                    "test"
                ):

                    (
                        outcome,
                        score,
                        rules_str,
                        inconsistent_rules,
                        totally_incomplete_rules,
                    ) = federated_test(
                        program=program,
                        store=store,
                        nb_client=nb_client,
                        round_id=round_id,
                    )

                tFedPopper += (
                    timer()
                    - start_fed
                )

                st.stats.total_programs += 1

                hypothesis_log.append(
                    {
                        "sequence_number": int(round_id),
                        "hypothesis": "\n".join(rules_str),
                        "score": float(score),
                        "epsilon_positive": str(outcome[0]),
                        "epsilon_negative": str(outcome[1]),
                        "is_final_validation": False,
                        "client_outcomes": [
                            dict(item) for item in LAST_CLIENT_OUTCOMES
                        ],
                        "inconsistent_rules": [
                            bool(x) for x in inconsistent_rules
                        ],
                        "totally_incomplete_rules": [
                            bool(x) for x in totally_incomplete_rules
                        ],
                    }
                )

                print(
                    f"[Program #{round_id}] "
                    f"outcome={outcome}, "
                    f"score={score}"
                )

                print(
                    "[Program feedback] "
                    f"inconsistent="
                    f"{inconsistent_rules}, "
                    f"totally_incomplete="
                    f"{totally_incomplete_rules}"
                )

                # ------------------------------------------
                # UPDATE BEST
                # ------------------------------------------

                if (
                    best_score is None
                    or score > best_score
                ):

                    best_score = score

                    best_rules_str = list(
                        rules_str
                    )

                    best_program = program

                    best_round = round_id

                # ------------------------------------------
                # STOP CONDITION
                # ------------------------------------------

                if outcome == (
                    "all",
                    "none",
                ):
                    print(
                        "\nSolution found "
                        "(ALL, NONE)"
                    )

                    final_round = round_id + 1

                    tell_final_hypothesis(
                        store=store,
                        hypothesis=rules_str,
                        tour=final_round,
                    )

                    found_solution = True
                    exact_solution_found = True
                    break

                # ------------------------------------------
                # BUILD / GROUND / ADD
                #
                # IMPORTANT:
                # Same build_rules_server() as Flower.
                # ------------------------------------------

                start_symbolic = timer()

                with st.stats.duration(
                    "build"
                ):

                    rules = build_rules_server(
                        st.settings,
                        st.stats,
                        st.constrainer,
                        st.tester,
                        program,
                        before,
                        min_clause,
                        outcome,
                        inconsistent_rules,
                        totally_incomplete_rules,
                    )

                with st.stats.duration(
                    "ground"
                ):

                    rules = ground_rules(
                        st.stats,
                        st.grounder,
                        st.solver.max_clauses,
                        st.solver.max_vars,
                        rules,
                    )

                with st.stats.duration(
                    "add"
                ):

                    st.solver.add_ground_clauses(
                        rules
                    )

                tCentralPopper += (
                    timer()
                    - start_symbolic
                )

                round_id += 1

        if not found_solution:
            # Search space exhausted (every literal size tried, no
            # exact solution) — same gap as the TIMEOUT case: without
            # this, tell_final_hypothesis() would never be called at
            # all here, leaving clients blocked waiting on a round that
            # will never come.
            print(
                "\nSearch space exhausted — no exact solution found."
            )

            (
                validated_rules_str,
                round_id,
            ) = finalize_with_best_hypothesis(
                store=store,
                best_program=best_program,
                nb_client=nb_client,
                round_id=round_id,
            )

            if validated_rules_str is not None:
                best_rules_str = validated_rules_str

    finally:

        try:

            store.send(
                b"close"
            )

            store.recv(
                1024
            )

        except Exception:
            pass

        store.close()

    # ==================================================
    # FINAL SUMMARY
    # ==================================================

    global_time = (
        timer()
        - start_time
    )

    print(
        "\n========== FINAL SUMMARY =========="
    )

    print(
        f"Total programs explored : "
        f"{st.stats.total_programs}"
    )

    print(
        f"Total execution time    : "
        f"{global_time:.4f}s"
    )

    if best_rules_str:

        print(
            f"\nBest hypothesis found "
            f"at round {best_round} "
            f"(score={best_score})"
        )

        for rule in best_rules_str:
            print(
                " ",
                rule,
            )

    else:

        print(
            "No valid hypothesis found."
        )

    # ==================================================
    # PERFORMANCE
    # ==================================================

    print(
        "\n========== PERFORMANCE SUMMARY =========="
    )

    print(
        f"Total time           : "
        f"{global_time:.4f}s"
    )

    print(
        f"Time in Popper core  : "
        f"{tCentralPopper:.4f}s"
    )

    print(
        f"Time in Federation   : "
        f"{tFedPopper:.4f}s"
    )

    if global_time > 0:

        print(
            f"Coordination ratio   : "
            f"{tFedPopper / global_time:.2%}"
        )

    else:

        print(
            "Coordination ratio   : N/A"
        )

    print(
        "\n========== SERVER TIMING =========="
    )

    st.stats.show()

    # ==================================================
    # PERSIST RESULT (server_result.json)
    #
    # Mirrors engines/collaboration/server.py's output so
    # core.launcher._run_coordination can read it back and save it to
    # the database via ServerResult/repository.save_server_result,
    # exactly like the Collaboration path already does.
    #
    # Known gap: unlike Collaboration, this server never computes
    # tp/fn/tn/fp for the best hypothesis (no final re-evaluation step
    # against the whole dataset exists yet) — they're written as 0
    # rather than guessed. best_score (from federated_test's scoring)
    # is used as final_score instead.
    # ==================================================

    if args.output_dir:

        output_dir = os.path.abspath(args.output_dir)
        os.makedirs(output_dir, exist_ok=True)

        federation_ratio = (
            tFedPopper / global_time if global_time > 0 else 0.0
        )

        result_payload = {
            "solution": (
                "\n".join(best_rules_str) if best_rules_str else None
            ),
            "solution_found": exact_solution_found,
            "total_time": float(startup_time + global_time),
            "startup_time": float(startup_time),
            "learning_time": float(global_time),
            "popper_time": float(tCentralPopper),
            "federation_time": float(tFedPopper),
            "federation_ratio": float(federation_ratio),
            "number_of_rounds": int(round_id),
            "number_of_programs": int(st.stats.total_programs),
            "final_score": float(best_score) if best_score is not None else 0.0,
            "tp": 0,
            "fn": 0,
            "tn": 0,
            "fp": 0,
        }

        with open(
            os.path.join(output_dir, "hypothesis_log.json"),
            "w",
            encoding="utf-8",
        ) as log_file:
            json.dump(hypothesis_log, log_file, indent=2)

        result_path = os.path.join(
            output_dir, "server_result.json"
        )

        with open(result_path, "w", encoding="utf-8") as result_file:
            json.dump(result_payload, result_file, indent=2)

        print(
            f"\n[srvpopper] Wrote server result to {result_path}"
        )


# ======================================================
#  RUN
# ======================================================

if __name__ == "__main__":

    # Timing mode now comes from --timing-mode (default "wall"), so it
    # matches whatever the launcher/UI selected instead of being fixed
    # here. Pass no override — run_server() derives it from args.
    run_server()