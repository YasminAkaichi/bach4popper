# Bach4Popper

Distributed Inductive Logic Programming via Coordination

Bach4Popper is a distributed orchestration framework for Inductive Logic Programming (ILP).
It decomposes Popper’s classical generate–test–constrain loop into coordinated agents communicating through a shared store.

This repository embeds Popper v1.1.0 directly under external/popper, ensuring full reproducibility without requiring a separate Popper installation.


## Repository Overview
```bash
Bach4Popper/
 ├── bach4popper/          # Coordination and orchestration logic
 ├── external/popper/      # Embedded Popper ILP engine
 ├── store/                # Shared blackboard (STORE process)
 ├── datasets/             # Example datasets (modifiable paths)
 ├── srvpopper.py          # Central coordination server
 ├── clipopper.py          # Distributed ILP client
 └── requirements.txt
```

## System Requirements

The system relies on symbolic reasoning tools used by Popper.

Please install:

Python ≥ 3.10

SWI-Prolog

Clingo (ASP solver)

Check installation:
```bash
swipl --version
clingo --version
```

## Installation

Clone the repository:
```bash
git clone https://github.com/<your-username>/Bach4Popper.git
cd Bach4Popper
```

Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate
```

Install required Python packages:
```bash
pip install -r requirements.txt
pip install parsimonious
```

parsimonious is required for the coordination layer (grammar-based parsing inspired by BLP-style coordination).

## Running Bach4Popper

The system is composed of several coordinated processes that must be launched in separate terminals.

You will need five terminals.

### Step 1 — Launch the STORE (Shared Blackboard)

Terminal 1:
```bash
python store/bb_popper.py
```

This starts the coordination space where agents exchange symbolic information.

### Step 2 — Launch the Central Server (Coordinator)

Terminal 2:
```bash
python srvpopper.py
```

The server:

orchestrates rounds,

aggregates hypotheses,

controls termination.

### Step 3 — Launch Distributed Clients

Open three additional terminals:

Terminal 3:
```bash
python clipopper1.py
```

Terminal 4:
```bash
python clipopper2.py
```

Terminal 5:
```bash
python clipopper3.py
```

Each client runs a local Popper instance over its data partition and communicates outcomes to the STORE.

## Dataset Configuration

Dataset paths can be modified directly inside:

clipopper1.py, clipopper2.py, clipopper3.py

srvpopper.py

Example:

DATASET_PATH = = "Downloads/Bach4Popper/zendo1_part1"

Update this path to match your local dataset location if necessary.

## How It Works (Conceptually)

Instead of sharing gradients (as in federated learning), Bach4Popper exchanges symbolic outcomes:

Clients generate hypotheses locally.

Hypotheses are tested using Popper.

Results are sent to the STORE.

The server aggregates symbolic evidence and drives the search.

This enables a distributed form of ILP while preserving interpretability.


## Minimal Execution Checklist

If execution fails, verify:
```bash
python -c "import pyswip"
swipl --version
clingo --version
```

All must succeed before running Bach4Popper.

## Research Context

Bach4Popper explores how coordination models can distribute symbolic learning systems, enabling ILP to operate in decentralized environments while maintaining declarative semantics.
