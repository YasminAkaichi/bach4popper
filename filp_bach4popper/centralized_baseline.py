"""
Centralized Popper run (the baseline).

Runs Popper 1.1.0 (the bundled popper-core) once, on the whole dataset, with no
store, no server and no clients. It is started as its own process by
``python -m filp_bach4popper centralized``, because the timeout of popper-core
uses signal.alarm(), which only works in the main thread of a process.

Writes a single JSON file, --output-dir/server_result.json, in the same shape as
the server of a Bach4Popper run, so that the two can be compared directly.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
POPPER_CORE_PATH = PACKAGE_DIR / "popper-core"

if str(POPPER_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(POPPER_CORE_PATH))


def main() -> None:
    parser = argparse.ArgumentParser(description="Centralized (non-federated) Popper run")
    parser.add_argument("--dataset", required=True, help="Path to the dataset directory (exs.pl / bk.pl / bias.pl)")
    parser.add_argument("--timeout", type=float, default=25.0, help="Max search time in seconds")
    parser.add_argument("--output-dir", required=True, help="Directory to write server_result.json into")
    args = parser.parse_args()

    dataset_directory = Path(args.dataset)
    output_directory = Path(args.output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)

    from popper.util import Settings
    from popper.loop import learn_solution

    settings = Settings(
        bias_file=str(dataset_directory / "bias.pl"),
        ex_file=str(dataset_directory / "exs.pl"),
        bk_file=str(dataset_directory / "bk.pl"),
        timeout=args.timeout,
        # Same limit as the federated approaches (set by the launcher).
        eval_timeout=float(__import__("os").environ.get("FILP_EVAL_TIMEOUT", "0.1")),
    )

    start_time = time.perf_counter()
    hypothesis_code, stats = learn_solution(settings)
    total_time = time.perf_counter() - start_time

    solution_found = hypothesis_code is not None

    prog_stats = stats.solution or (
        stats.best_programs[-1] if stats.best_programs else None
    )

    if prog_stats is not None:
        tp, fn, tn, fp = prog_stats.conf_matrix
    else:
        tp = fn = tn = fp = 0

    total_predictions = tp + fn + tn + fp
    accuracy = (tp + tn) / total_predictions if total_predictions else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    # Same per-stage timing breakdown Popper's own `stats.show()` prints
    # to the console (generate / ground / test / add, etc.) — exposed
    # here so the UI can show it too.
    duration_summary = [
        {
            "operation": summary.operation,
            "called": summary.called,
            "total": summary.total,
            "mean": summary.mean,
            "maximum": summary.maximum,
        }
        for summary in stats.duration_summary()
    ]

    result = {
        "solution": hypothesis_code,
        "solution_found": solution_found,
        "total_time": total_time,
        "startup_time": 0.0,
        "learning_time": total_time,
        "popper_time": total_time,
        "federation_time": 0.0,
        "federation_ratio": 0.0,
        "number_of_rounds": 1,
        "number_of_programs": stats.total_programs,
        "final_score": float(tp + tn),
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "duration_summary": duration_summary,
    }

    result_path = output_directory / "server_result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(
        f"[centralized] {'Solution found' if solution_found else 'No solution'} "
        f"in {total_time:.2f}s ({stats.total_programs} programs tested). "
        f"Result written to {result_path}"
    )


if __name__ == "__main__":
    main()
