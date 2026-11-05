"""Aggregation of the answers of the clients (Learning by Coordination).

Every client answers, for the hypothesis H of the round, a pair
(outcome on E+, outcome on E-) with outcome in {all, some, none}.
The server aggregates them as follows, separately for E+ and for E-:

    ALL  if every client answers ALL,
    NONE if every client answers NONE,
    SOME in every other case.

The table has to be complete (the 9 pairs): with a missing pair the
accumulated value would silently be kept, e.g. (none, some) -> none, and the
search would no longer be the centralized one.
"""

_OUTCOMES = ("all", "some", "none")

AGG_TABLE_POS = {(a, b): (a if a == b else "some") for a in _OUTCOMES for b in _OUTCOMES}
AGG_TABLE_NEG = dict(AGG_TABLE_POS)


def aggregate_outcomes(outcomes):
    """outcomes: list of (E+ outcome, E- outcome). Returns the aggregated pair."""
    if len(outcomes) == 0:
        return ("none", "none")

    e_plus, e_minus = outcomes[0]
    for ep, em in outcomes[1:]:
        e_plus = AGG_TABLE_POS[(e_plus, ep)]
        e_minus = AGG_TABLE_NEG[(e_minus, em)]
    return (e_plus, e_minus)
