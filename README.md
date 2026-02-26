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
 ├── bbpopper.py           # Central coordination server
 ├── srvpopper.py          # Central coordination server
 ├── clipopper*.py         # Distributed ILP client
 ├── bbpopper.py           # Central coordination server
 └── requirements.txt
```

## Recommended Execution: Docker (Reproducible Environment)

To guarantee platform-independent reproducibility, Bach4Popper is distributed with a Docker configuration that encapsulates:

Python ≥ 3.10

SWI-Prolog

Clingo (ASP solver)

All Python dependencies

The embedded Popper engine

No manual installation of symbolic reasoning tools is required.

## Running with Docker (Recommended)

### 1. Clone the Repository
git clone https://github.com/<your-username>/Bach4Popper.git
cd Bach4Popper
### 2. Build the Docker Image
```bash
docker build -t bach4popper .
```

This step installs all dependencies and prepares a fully configured execution environment.
### 3. Launch the Container
```bash
docker run -it --name bach bach4popper
```
You are now inside the reproducible environment.

### 4. Start the Coordination STORE
```bash
python3 bbpopper.py
```
This launches the shared tuple-space used for coordination.

### 5. Open Additional Shells (Same Container)

From another terminal:
```bash
docker exec -it bach bash
```

### 6. Start the Server
```bash
python3 srvpopper.py
```
The server: generates hypotheses, manages constraints andaggregates feedback.

### 7. Launch Distributed Clients

Open additional shells and run:
```bash
python3 clipopper1.py
```
```bash
python3 clipopper2.py
```
```bash
python3 clipopper3.py
```

Each client evaluates hypotheses locally and returns symbolic feedback.


## Dataset Structure

Datasets are partitioned to simulate distributed ownership:
```bash
datasets/
 ├── zendo1/
 ├── zendo1_part1/
 ├── zendo1_part2/
 └── zendo1_part3/
```
Each client accesses only its local partition.
No raw data is shared during learning.

## Optional: Running Without Docker (Manual Setup)

This is not recommended, but possible.

Requirements:
```bash
Python ≥ 3.10
SWI-Prolog
Clingo
Numpy
```
Check installation:
```bash
swipl --version
clingo --version
```
Install Python dependencies:
```bash
pip install -r requirements.txt
pip install ./external/popper
```
Then follow the same execution steps as above.



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
