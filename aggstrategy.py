# aggstrategy.py
# ------------------------------------------------------
#  FILP Distributed Popper Aggregation Logic
#  Used by srvpopper.py (Option A)
# ------------------------------------------------------

import numpy as np
from popper.loop import build_rules, decide_outcome, ground_rules, Outcome
from popper.generate import generate_program
from popper.core import Clause
from logging import getLogger

log = getLogger(__name__)

# ------------------------------------------------------
#  OUTCOME ENCODING / DECODING
# ------------------------------------------------------

OUTCOME_ENCODING = {"all": 1, "some": 2, "none": 3}
OUTCOME_DECODING = {1: "all", 2: "some", 3: "none"}

AGG_TABLE_POS = {
    ("all","all"): "all",
    ("all","some"): "some",
    ("all","none"): "some",
    ("some","some"): "some",
    ("some","none"): "some",
    ("none","none"): "none",
}

AGG_TABLE_NEG = {
    ("some","some"): "some",
    ("some","none"): "some",
    ("none","some"): "some",
    ("none","none"): "none",
}


# ------------------------------------------------------
#   OUTCOME AGGREGATION
# ------------------------------------------------------

def aggregate_outcomes(outcomes):
    """
    outcomes: list of tuples ('all'/'some'/'none', 'all'/'some'/'none')
    Returns aggregated (E+, E-)
    """

    if len(outcomes) == 0:
        return ("none","none")

    Eplus, Eminus = outcomes[0]

    for (ep, em) in outcomes[1:]:
        # positive
        Eplus = AGG_TABLE_POS.get((Eplus, ep), Eplus)
        # negative
        Eminus = AGG_TABLE_NEG.get((Eminus, em), Eminus)

    return (Eplus, Eminus)


# ------------------------------------------------------
#   FILP Distributed Popper Step (Server-Side)
# ------------------------------------------------------


def aggregate_popper(
    outcome,                 # (ε⁺, ε⁻) or (None, None)
    settings,
    solver,
    grounder,
    constrainer,
    tester,                  # StructuralTester
    stats,
    current_min_clause,
    current_before,
    current_hypothesis,
    clause_size,
):
    """
    One federated Popper step.
    EXACT equivalent of ONE iteration of centralized Popper,
    using symbolic outcome only (FILP-safe).
    """

    log.info("===== FedPopper aggregate_popper =====")
    ep = en = outcome
    has_feedback = outcome != (None, None)

    if has_feedback:
        log.info(f"Outcome received: {outcome}")
    else:
        log.info("No test feedback yet (initial hypothesis generation)")

    # ---------------------------------------------------------
    # 1) Add constraints ONLY if feedback exists
    # ---------------------------------------------------------
    if has_feedback and current_hypothesis:
        log.debug("Building constraints from previous hypothesis")

        constraints = build_rules(
            settings=settings,
            stats=stats,
            constrainer=constrainer,
            tester=tester,              # Structural only
            program=current_hypothesis,
            before=current_before,
            min_clause=current_min_clause,
            outcome=outcome,
        )

        grounded = ground_rules(
            stats,
            grounder,
            solver.max_clauses,
            solver.max_vars,
            constraints,
        )

        solver.add_ground_clauses(grounded)

    # ---------------------------------------------------------
    # 2) Generate ONE hypothesis (solver.get_model)
    # ---------------------------------------------------------
    model = solver.get_model()
    
    #if not model:
    #    clause_size += 1
    #    solver.update_number_of_literals(clause_size)
    #    stats.update_num_literals(clause_size)

    #        log.info(f"No model left, increasing clause size to {clause_size}")

    #    return (        [np.array([], dtype="<U1000")],current_min_clause,           current_before,            clause_size,            solver,            False,            current_hypothesis,)
    
    if not model:
        clause_size += 1

        if clause_size >= settings.max_literals:
            log.info(f"Reached max_literals={settings.max_literals}. Search exhausted.")
            return (
                [np.array([], dtype="<U1000")],
                current_min_clause,
                current_before,
                clause_size,
                solver,
                True,              # <-- FLAG D’ARRÊT
                current_hypothesis,
            )

        solver.update_number_of_literals(clause_size)
        stats.update_num_literals(clause_size)

        return (
            [np.array([], dtype="<U1000")],
            current_min_clause,
            current_before,
            clause_size,
            solver,
            False,
            current_hypothesis,
        )


    # Decode hypothesis
    current_rules, before, min_clause = generate_program(model)

    # Register program structurally (no scores)
    #stats.register_program(current_rules, None)

    # ---------------------------------------------------------
    # 3) Solution check (Popper stopping condition)
    # ---------------------------------------------------------
    if has_feedback and outcome == (Outcome.ALL, Outcome.NONE):
        log.info("Popper solution found")

        rules_arr = np.array(
            [Clause.to_code(r) for r in current_rules],
            dtype="<U1000",
        )

        return (
            [rules_arr],
            min_clause,
            before,
            clause_size,
            solver,
            True,               # solved
            current_rules,
        )

    # ---------------------------------------------------------
    # 4) Normal continuation
    # ---------------------------------------------------------
    rules_arr = np.array(
        [Clause.to_code(r) for r in current_rules],
        dtype="<U1000",
    )

    return (
        [rules_arr],
        min_clause,
        before,
        clause_size,
        solver,
        False,
        current_rules,
    )


def aggregate_popperx(
    outcome_pair,
    settings,
    solver,
    grounder,
    constrainer,
    tester,
    stats,
    current_min_clause,
    current_before,
    current_hypothesis,
    clause_size
):
    """
    Performs ONE Popper iteration:
      - If no_constraints=True → only generate()
      - Else → build constraints + ground + add + generate

    This mirrors FILP Flower’s version but adapted for BLPy sockets.
    """

    # ------------------------------------------------------
    # 1) Normalize outcomes
    # ------------------------------------------------------

    if outcome_pair is None:
        # "initial round": do not build constraints
        normalized_outcome = (Outcome.SOME, Outcome.SOME)
    else:
        Eplus, Eminus = outcome_pair

        # FILP rule: negative cannot be "all"
        if Eminus == "all":
            Eminus = "some"

        normalized_outcome = (
            Outcome.ALL if Eplus=="all" else Outcome.SOME if Eplus=="some" else Outcome.NONE,
            Outcome.ALL if Eminus=="all" else Outcome.SOME if Eminus=="some" else Outcome.NONE,
        )

    # ------------------------------------------------------
    # 2) APPLY CONSTRAINTS (unless disabled)
    # ------------------------------------------------------

    has_feedback = (
    outcome_pair is not None
    and outcome_pair != ("none", "none")
)

    if has_feedback and (current_hypothesis is not None):

        constraints = build_rules(
            settings=settings,
            stats=stats,
            constrainer=constrainer,
            tester=tester,
            program=current_hypothesis,
            before=current_before,
            min_clause=current_min_clause,
            outcome=normalized_outcome,
        )

        grounded = ground_rules(
            stats,
            grounder,
            solver.max_clauses,
            solver.max_vars,
            constraints,
        )

        solver.add_ground_clauses(grounded)


    # ------------------------------------------------------
    # 3) GENERATE a new model
    # ------------------------------------------------------

    model = solver.get_model()
    if not model:
        empty = np.array([], dtype="<U1000")
        clause_size += 1
        solver.update_number_of_literals(clause_size)
        stats.update_num_literals(clause_size)
        return [empty], current_min_clause, current_before, clause_size, solver, False, current_hypothesis

    new_rules, new_before, new_min_clause = generate_program(model)

    # ------------------------------------------------------
    # 4) CHECK STOPPING: global outcome ALL/NONE
    # ------------------------------------------------------

    if outcome_pair == ("all","none"):
        rules_bytes = [Clause.to_code(r) for r in new_rules]
        arr = np.array(rules_bytes, dtype="<U1000")
        return [arr], new_min_clause, new_before, clause_size, solver, True, new_rules

    # ------------------------------------------------------
    # 5) STANDARD RETURN
    # ------------------------------------------------------

    rules_bytes = [Clause.to_code(r) for r in new_rules]
    arr = np.array(rules_bytes, dtype="<U1000")

    return [arr], new_min_clause, new_before, clause_size, solver, False, new_rules