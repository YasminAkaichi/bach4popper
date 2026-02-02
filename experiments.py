import os
import csv
import time
import json
import signal
import subprocess
from pathlib import Path

ROOT = Path("runs")
ROOT.mkdir(exist_ok=True)

STORE_CMD  = ["python3", "bbpopper.py"]          # <-- store
SERVER_CMD = ["python3", "server.py"]         # <-- server
CLIENT_CMD = ["python3", "client1.py"]      # <-- client

NB_RUNS = 100
NB_CLIENTS = 3
#/Users/yasmineakaichi/Downloads/Bach-Popper-dist-v1/trains/bias.pl
PATH_DIR_SERVER = "trains"
PATH_DIR_CLIENTS = [
    "trains_part1",
    "trains_part2",
    "trains_part3",
]

RUN_TIMEOUT_SEC = 300  # stop un run si ça dépasse 5 min

def start_proc(cmd, log_path, extra_env=None):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(log_path, "w", buffering=1)  # line-buffered
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    p = subprocess.Popen(
        cmd,
        stdout=f,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        preexec_fn=os.setsid  # permet kill du groupe
    )
    return p, f

def kill_proc(p):
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except Exception:
        pass

def wait_all(procs, timeout):
    t0 = time.time()
    while True:
        alive = [p for p in procs if p.poll() is None]
        if not alive:
            return True
        if time.time() - t0 > timeout:
            return False
        time.sleep(0.2)

def read_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None

summary_csv = ROOT / "summary.csv"
with open(summary_csv, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["run_id", "converged", "rounds", "time_seconds", "server_metrics_ok", "clients_metrics_ok"])

for run_id in range(NB_RUNS):
    run_dir = ROOT / f"run_{run_id:03d}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # chemins de metrics (écrits par serveur/clients)
    server_metrics = run_dir / "server_metrics.json"
    client_metrics = [run_dir / f"client_{i}_metrics.json" for i in range(1, NB_CLIENTS+1)]

    store_log  = run_dir / "store.log"
    server_log = run_dir / "server.log"
    client_logs = [run_dir / f"client_{i}.log" for i in range(1, NB_CLIENTS+1)]

    procs = []
    files = []

    try:
        # 1) Start store
        store_p, store_f = start_proc(STORE_CMD, store_log)
        procs.append(store_p); files.append(store_f)
        time.sleep(0.5)  # laisse le store écouter

        # 2) Start server
        # -> passer run_id et out path via env (simple) ou arguments CLI (mieux)
        server_env = {
            "RUN_ID": str(run_id),
            "OUT_METRICS": str(server_metrics),
            "PATH_DIR": PATH_DIR_SERVER,
            "NB_CLIENTS": str(NB_CLIENTS),
        }
        server_p, server_f = start_proc(SERVER_CMD, server_log, extra_env=server_env)
        procs.append(server_p); files.append(server_f)
        time.sleep(0.5)

        # 3) Start clients
        for i in range(1, NB_CLIENTS+1):
            env = {
                "RUN_ID": str(run_id),
                "CLIENT_ID": str(i),
                "OUT_METRICS": str(client_metrics[i-1]),
                "PATH_DIR": PATH_DIR_CLIENTS[i-1],
            }
            p, f2 = start_proc(CLIENT_CMD, client_logs[i-1], extra_env=env)
            procs.append(p); files.append(f2)

        # 4) Wait with timeout
        ok = wait_all(procs, RUN_TIMEOUT_SEC)
        if not ok:
            # timeout -> kill everything
            for p in procs:
                if p.poll() is None:
                    kill_proc(p)

        # 5) Read metrics written by processes
        sm = read_json(server_metrics)
        cms = [read_json(p) for p in client_metrics]

        server_ok = sm is not None
        clients_ok = all(c is not None for c in cms)

        # fallback if server didn't write
        converged = sm.get("converged") if sm else False
        rounds = sm.get("rounds") if sm else None
        secs = sm.get("time_seconds") if sm else None

        with open(summary_csv, "a", newline="") as f:
            w = csv.writer(f)
            w.writerow([run_id, converged, rounds, secs, server_ok, clients_ok])

        print(f"[run {run_id:03d}] done. server_ok={server_ok} clients_ok={clients_ok} converged={converged}")

    finally:
        # close files
        for fp in files:
            try: fp.close()
            except Exception: pass

        # ensure kill leftover
        for p in procs:
            if p.poll() is None:
                kill_proc(p)
