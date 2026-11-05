"""Command line: python -m filp_bach4popper <command> [options]"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="filp_bach4popper",
        description="Bach4Popper: Learning by Coordination for federated ILP",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--dataset", required=True,
                       help="dataset name (in datasets/) or path to a Popper folder "
                            "containing bias.pl, bk.pl and exs.pl")
        p.add_argument("--clients", type=int, default=3)
        p.add_argument("--partition", choices=["iid", "non_iid"], default="iid")
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--output", default="results", help="results folder")

    run = sub.add_parser("run", help="run Bach4Popper (store + server + clients)")
    common(run)
    run.add_argument("--timeout", type=int, default=600, help="search timeout in seconds")
    run.add_argument("--timing-mode", choices=["wall", "cpu"], default="wall")
    run.add_argument("--hybrid", action="store_true",
                     help="also run the complete search of client 0 (centralized, whole dataset)")

    run.add_argument("--verbose", action="store_true",
                     help="show the output of the store, server and clients (default: logs/*.log files)")

    cen = sub.add_parser("centralized", help="centralized Popper on the whole dataset")
    common(cen)
    cen.add_argument("--timeout", type=int, default=600)

    prep = sub.add_parser("prepare", help="only partition the dataset (no Prolog needed)")
    common(prep)

    args = parser.parse_args(argv)

    from filp_bach4popper import pipeline

    if args.command == "run":
        pipeline.run(args.dataset, args.clients, args.partition, args.seed,
                     args.timeout, args.output, args.timing_mode, args.hybrid, args.verbose)
    elif args.command == "centralized":
        pipeline.centralized(args.dataset, args.timeout, args.output, args.seed,
                             args.clients, args.partition)
    else:
        source = pipeline.resolve_dataset(args.dataset)
        out = Path(args.output).resolve() / pipeline.run_name(
            source, args.clients, args.partition, args.seed)
        split = pipeline.prepare(source, args.clients, args.partition, args.seed, out / "data")
        print(pipeline.describe(split))
        print(f"Partitions written to {split.root}")
