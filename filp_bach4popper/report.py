"""Console summary of a Bach4Popper run."""

from __future__ import annotations

import json
from pathlib import Path


def _f(value, digits=2):
    if value is None:
        return "-"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _search_row(label: str, r: dict) -> str:
    return (
        f"{label:<24}{'yes' if r.get('solution_found') else 'no':>9}"
        f"{_f(r.get('number_of_rounds')):>8}{_f(r.get('number_of_programs')):>10}"
        f"{_f(r.get('learning_time')):>13}{_f(r.get('popper_time')):>9}"
        f"{_f(r.get('federation_time')):>15}"
    )


def print_summary(main: dict, client0: dict | None = None, title: str = "Bach4Popper") -> None:
    print()
    print(f"{'Search':<24}{'Solution':>9}{'Rounds':>8}{'Programs':>10}{'Learning(s)':>13}{'Core(s)':>9}{'Federation(s)':>15}")
    print("-" * 88)
    print(_search_row(title, main))
    if client0 is not None:
        print(_search_row("Client 0 (centralized)", client0))
    print("\nLearned program:")
    print(main.get("solution") or "(none)")


def _compare(fed_log, c0_log) -> str:
    if not fed_log or not c0_log:
        return "hypothesis logs not available"
    for i, (a, b) in enumerate(zip(fed_log, c0_log), start=1):
        if a["hypothesis"] != b["hypothesis"]:
            return (f"the two searches diverge at round {i}: the aggregated outcome of the clients "
                    f"({a['epsilon_positive']}, {a['epsilon_negative']}) differs from the outcome of client 0")
    if len(fed_log) == len(c0_log):
        return f"identical: the two searches generate the same {len(fed_log)} programs in the same order"
    return (f"the first {min(len(fed_log), len(c0_log))} programs are identical, then one search "
            f"stops earlier ({len(fed_log)} vs {len(c0_log)} programs)")


def print_run(out: Path, hybrid: bool) -> None:
    fed_dir = out / "federated"
    fed = _load(fed_dir / "server_result.json") or {}
    cfg = _load(out / "run_config.json") or {}
    print(f"\n=== {out.name} ===")

    print("\nClients (evaluation of the programs on their own examples)")
    print(f"{'Client':>6}{'pos':>6}{'neg':>6}{'programs':>10}{'eval(s)':>10}{'avg(ms)':>9}")
    print("-" * 47)
    for path in sorted(fed_dir.glob("client_*_result.json")):
        c = _load(path) or {}
        avg = c.get("average_eval_wall")
        print(f"{c.get('client_id', '?'):>6}{_f(c.get('number_of_positive_examples')):>6}"
              f"{_f(c.get('number_of_negative_examples')):>6}{_f(c.get('number_of_evaluations')):>10}"
              f"{_f(c.get('total_eval_wall')):>10}{_f(avg * 1000 if avg is not None else None, 1):>9}")

    c0 = _load(out / "client0" / "server_result.json") if hybrid else None
    print_summary(fed, c0, f"Coordination (K={cfg.get('clients', '?')})")

    if hybrid:
        fl = _load(fed_dir / "hypothesis_log.json")
        cl = _load(out / "client0" / "hypothesis_log.json")
        print(f"\nHybrid evaluation: {_compare(fl, cl)}")

    print(f"\nFiles: {fed_dir}/ (server_result.json, client_<i>_result.json, hypothesis_log.json, *.log)")
