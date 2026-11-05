"""End-to-end Bach4Popper run, without any user interface.

    prepare()      read the dataset, partition the examples among K clients,
                   write the partitions to disk;
    run()          prepare + start the Bach store, the server and the K clients;
    centralized()  Popper once, on the whole dataset (the baseline);
    run(hybrid=True) additionally repeats the WHOLE generate-test-constrain
                   search with a single client that holds the whole dataset
                   (client 0), so that the two searches can be compared round
                   by round (hybrid evaluation protocol).
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from filp_bach4popper.partitioning.dataset_reader import read_dataset
from filp_bach4popper.partitioning.partitioner import partition_dataset
from filp_bach4popper.partitioning.writer import write_partitions
from filp_bach4popper.paths import BACH_DIR, DATASETS_DIR, PACKAGE_ROOT, child_environment


@dataclass
class Split:
    client_dirs: list[Path]
    root: Path
    partitions: list


def resolve_dataset(name_or_path: str) -> Path:
    path = Path(name_or_path)
    if path.is_dir():
        return path.resolve()
    candidate = DATASETS_DIR / name_or_path
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(f"Dataset '{name_or_path}' not found (looked in {DATASETS_DIR}).")


def run_name(dataset: Path, clients: int, partition: str, seed: int) -> str:
    return f"{dataset.name}_k{clients}_{partition}_seed{seed}"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def prepare(dataset: Path, clients: int, partition: str, seed: int, output_root: Path) -> Split:
    data = read_dataset(dataset)
    parts = partition_dataset(
        dataset=data, number_of_clients=clients, strategy=partition, random_seed=seed
    )
    root = write_partitions(
        dataset_name=dataset.name, partitions=parts, strategy=partition,
        random_seed=seed, output_root=output_root,
    )
    dirs = [root / f"{dataset.name}_part{i}" for i in range(1, clients + 1)]
    return Split(dirs, root, parts)


def describe(split: Split) -> str:
    lines = ["Client   positives  negatives"]
    for p in split.partitions:
        lines.append(
            f"{p.client_id:>6}   {len(p.positive_examples):>9}  {len(p.negative_examples):>9}"
        )
    return "\n".join(lines)


def _tail(path: Path, lines: int = 25) -> str:
    try:
        return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


def _search(source: Path, client_dirs: list[Path], timeout: int, result_dir: Path,
            timing_mode: str, label: str, verbose: bool = False) -> dict:
    """One complete search: store + server + one client per partition."""
    result_dir.mkdir(parents=True, exist_ok=True)
    env = child_environment()
    port = free_port()
    address = f"127.0.0.1:{port}"
    processes: list[subprocess.Popen] = []
    logs = []

    def sink(name: str):
        """Quiet by default: the output of each process goes to <name>.log."""
        if verbose:
            return None
        handle = open(result_dir / f"{name}.log", "w", encoding="utf-8")
        logs.append(handle)
        return handle

    print(f"[bach4popper] {label}: {len(client_dirs)} client(s), store on {address}")
    try:
        store = subprocess.Popen(
            [sys.executable, "bbpopper.py", "--port", str(port)],
            cwd=BACH_DIR, env=env, stdout=sink("store"), stderr=subprocess.STDOUT,
        )
        processes.append(store)
        time.sleep(1)
        if store.poll() is not None:
            raise RuntimeError("The Bach store stopped during start-up.")

        server = subprocess.Popen(
            [sys.executable, "-m", "filp_bach4popper.server",
             "--dataset", str(source), "--clients", str(len(client_dirs)),
             "--timeout", str(timeout), "--store-address", address,
             "--timing-mode", timing_mode, "--output-dir", str(result_dir)],
            cwd=PACKAGE_ROOT, env=env, stdout=sink("server"), stderr=subprocess.STDOUT,
        )
        processes.append(server)
        time.sleep(1)
        if server.poll() is not None:
            raise RuntimeError("The Bach4Popper server stopped during start-up.\n"
                               + _tail(result_dir / "server.log"))

        clients = []
        for i, client_dir in enumerate(client_dirs, start=1):
            proc = subprocess.Popen(
                [sys.executable, "-m", "filp_bach4popper.client",
                 "--client-id", str(i), "--dataset", str(client_dir),
                 "--store-address", address, "--output-dir", str(result_dir)],
                cwd=PACKAGE_ROOT, env=env, stdout=sink(f"client_{i}"),
                stderr=subprocess.STDOUT,
            )
            processes.append(proc)
            clients.append(proc)

        if server.wait() != 0:
            raise RuntimeError("The Bach4Popper server failed.\n"
                               + _tail(result_dir / "server.log"))
        # The clients keep waiting for the next round: once the server is done,
        # ask them to stop (they write their result file on SIGTERM).
        for proc in clients:
            if proc.poll() is None:
                proc.terminate()
        for proc in clients:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for handle in logs:
            handle.close()

    return json.loads((result_dir / "server_result.json").read_text(encoding="utf-8"))


def run(
    dataset: str,
    clients: int = 3,
    partition: str = "iid",
    seed: int = 42,
    timeout: int = 600,
    output: str | Path = "results",
    timing_mode: str = "wall",
    hybrid: bool = False,
    verbose: bool = False,
) -> Path:
    source = resolve_dataset(dataset)
    out = Path(output).resolve() / run_name(source, clients, partition, seed)
    out.mkdir(parents=True, exist_ok=True)

    split = prepare(source, clients, partition, seed, out / "data")
    print(f"[bach4popper] dataset={source.name} K={clients} partition={partition} seed={seed}")
    print(describe(split))
    federated = _search(source, split.client_dirs, timeout, out / "federated",
                        timing_mode, f"federated search (K={clients})", verbose)

    client0 = None
    if hybrid:
        whole = prepare(source, 1, "iid", seed, out / "data_client0")
        client0 = _search(source, whole.client_dirs, timeout, out / "client0",
                          timing_mode, "client 0 (centralized) search", verbose)

    (out / "run_config.json").write_text(json.dumps({
        "dataset": source.name, "clients": clients, "partition": partition,
        "seed": seed, "timeout": timeout, "timing_mode": timing_mode, "hybrid": hybrid,
    }, indent=2), encoding="utf-8")

    from filp_bach4popper.report import print_run
    print_run(out, hybrid)
    return out


def centralized(
    dataset: str,
    timeout: int = 600,
    output: str | Path = "results",
    seed: int = 42,
    clients: int = 3,
    partition: str = "iid",
) -> Path:
    """Popper (centralized baseline) on the whole dataset."""
    source = resolve_dataset(dataset)
    out = Path(output).resolve() / run_name(source, clients, partition, seed)
    result_dir = out / "centralized"
    result_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [sys.executable, "-m", "filp_bach4popper.centralized_baseline",
         "--dataset", str(source), "--timeout", str(timeout),
         "--output-dir", str(result_dir)],
        cwd=PACKAGE_ROOT, env=child_environment(), check=True,
    )
    from filp_bach4popper.report import print_summary
    result = json.loads((result_dir / "server_result.json").read_text(encoding="utf-8"))
    print_summary(result, None, title="Centralized Popper")
    return out
