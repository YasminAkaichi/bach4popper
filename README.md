# Bach4Popper

Command-line implementation of **Learning by Coordination** (Bach4Popper) for
federated ILP, extracted from the FILP platform (no user interface). The server
runs Popper's generate-test-constrain loop: it generates a program, each client
evaluates it on its own examples only and answers **ALL / SOME / NONE** (for the
positive and for the negative examples), and the server aggregates the answers
and builds the constraints (clause-level feedback included). No example, fact or
rule leaves a client. The server and the clients communicate through a small
shared store ([Bach](https://github.com/YasminAkaichi/bach4popper/tree/main/filp_bach4popper/bach)).

> **Relation to the published paper.** Bach4Popper was introduced in
> *Bach4Popper: Towards Federated Inductive Logic Programming Using
> Coordination* (Akaichi, Barkallah, Jacquet, Linden and Vanhoof, COORDINATION
> 2026). This repository goes beyond the published version: it adds IID and
> non-IID partitions, the **hybrid evaluation protocol** (a second, complete
> search by a client 0 that holds the whole dataset, compared round by round
> with the federated search), a centralized Popper baseline, and a per-client
> report (examples, programs evaluated, evaluation time). Results obtained with
> this code may therefore differ from, or complement, those reported in the
> paper.

## Citation

If you use this code, please cite the paper:

```bibtex
@inproceedings{akaichi2026bach4popper,
  title        = {Bach4Popper: Towards Federated Inductive Logic Programming Using Coordination},
  author       = {Akaichi, Yasmine and Barkallah, Manel and Jacquet, Jean-Marie and Linden, Isabelle and Vanhoof, Wim},
  booktitle    = {International Conference on Coordination Models and Languages},
  pages        = {136--156},
  year         = {2026},
  organization = {Springer}
}
```

## Install

```bash
cd bach4popper
python -m pip install -r requirements.txt
```

Popper 1.1.0 and the Bach store are bundled in `filp_bach4popper/popper-core`
and `filp_bach4popper/bach`; nothing else to clone. The original Popper is
available at [logic-and-learning-lab/Popper](https://github.com/logic-and-learning-lab/Popper);
the bundled copy contains the modifications needed by this code
(`build_rules_server`, `FederatedTester`, no dependency on `pkg_resources`).
Popper needs **SWI-Prolog** installed on the machine (`brew install swi-prolog`
on macOS). To use another copy of Popper, set `FILP_POPPER_PATH`.

## Docker (easiest way to try it)

Nothing to install except Docker: SWI-Prolog, Python, Popper and the store are
all inside the image.

```bash
docker build -t bach4popper .

# default demo: Zendo1, 3 clients, IID, with the hybrid evaluation
docker run --rm bach4popper

# any other run: the arguments are those of `python -m filp_bach4popper`
docker run --rm -v "$PWD/results:/app/results" bach4popper \
       run --dataset trains1000 --clients 5 --partition non_iid --hybrid

# your own dataset (a folder with bias.pl, bk.pl, exs.pl)
docker run --rm -v "$PWD/mydata:/data" -v "$PWD/results:/app/results" \
       bach4popper run --dataset /data --clients 3
```

With `-v "$PWD/results:/app/results"` the results (JSON files, logs) are kept
on your machine.

## Quick start

```bash
python -m filp_bach4popper run --dataset zendo1 --clients 3 --partition iid --seed 42 --hybrid
```

The output of the store, the server and the clients is written to
`results/.../*.log`; add `--verbose` to see it on the screen. Output
(Zendo1, 3 clients, IID, seed 42; times vary from one machine to another):

```
=== zendo1_k3_iid_seed42 ===

Clients (evaluation of the programs on their own examples)
Client   pos   neg  programs   eval(s)  avg(ms)
-----------------------------------------------
     1     7     7       194      0.06      0.3
     2     7     7       194      0.08      0.4
     3     6     6       194      0.06      0.3

Search                   Solution  Rounds  Programs  Learning(s)  Core(s)  Federation(s)
----------------------------------------------------------------------------------------
Coordination (K=3)            yes     193       194         2.08     0.50           1.56
Client 0 (centralized)        yes     193       194         1.90     0.49           1.40

Learned program:
zendo(A) :- small(B),piece(A,D),red(C),size(D,B),contact(D,C).

Hybrid evaluation: identical: the two searches generate the same 194 programs in the same order
```

The dataset is a parameter: replace `zendo1` with any folder of `datasets/`
(trains, trains1000, iggp-rps, mutagenesis, carcinogenesis,
noisy-alzheimer_acetyl, intubation) or with the path to your own Popper dataset
(`bias.pl`, `bk.pl`, `exs.pl`). The number of clients, the partition
(`iid` / `non_iid`), the seed and the timeout can be changed the same way.

## Other commands

```bash
# Same data, non-IID partition, 5 clients
python -m filp_bach4popper run --dataset trains1000 --clients 5 --partition non_iid

# Centralized Popper on the whole dataset
python -m filp_bach4popper centralized --dataset zendo1

# Only partition the data (no Prolog needed)
python -m filp_bach4popper prepare --dataset trains1000 --clients 10 --partition non_iid
```

## What happens

1. The examples are partitioned among `--clients` clients: `iid` (shuffled,
   round-robin) or `non_iid` (client *i* receives a share proportional to *i*
   of the positive examples and to *K+1-i* of the negative ones). Facts that
   describe an example go to its owner; shared facts and rules go to everyone.
2. A Bach store, the server and one process per client are started on a free
   local port.
3. In each round the server publishes a program; every client answers
   (outcome on E+, outcome on E−, score) and, for each separable clause,
   whether it is inconsistent or totally incomplete. The server aggregates
   (ALL / NONE only if all clients agree, SOME otherwise), builds the
   constraints and generates the next program, until a program with outcome
   (ALL, NONE) is found or the timeout expires.
4. With `--hybrid`, the whole search is repeated with a single client that
   holds the whole dataset (client 0), with the same seed, and the two
   `hypothesis_log.json` are compared round by round.

## Output

`results/<dataset>_k<K>_<partition>_seed<S>/`

| Path | Content |
|---|---|
| `federated/server_result.json` | learned program, rounds, programs tested, learning / Popper-core / federation times, score |
| `federated/client_<i>_result.json` | examples, programs evaluated, evaluation time of client *i* |
| `federated/hypothesis_log.json` | for each round: the program, the answer of every client, the aggregated outcome, the clause-level feedback |
| `federated/*.log` | output of the store, the server and the clients |
| `client0/` | the same files for the search of client 0 (with `--hybrid`) |
| `centralized/` | the baseline (command `centralized`) |
| `data/`, `data_client0/` | the generated client partitions |
| `run_config.json` | parameters of the run |

## Layout

```
filp_bach4popper/
  cli.py, pipeline.py      command line and orchestration
  srvpopper.py, clipopper.py  Bach4Popper server and client
  strategy/aggstrategy.py  aggregation of the answers (ALL / SOME / NONE)
  bach/                    coordination store (bbpopper.py)
  popper-core/             Popper 1.1.0 with build_rules_server and FederatedTester
  partitioning/            IID / non-IID partitioning, dataset writer
  centralized_baseline.py  Popper on the whole dataset
  report.py                console summary
```

## Licence

MIT (see `LICENSE`). Popper is distributed under its own licence
(`filp_bach4popper/popper-core/LICENSE`).
