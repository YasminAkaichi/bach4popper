"""Locations used by the standalone Bach4Popper package.

Popper 1.1.0 and the Bach coordination store are bundled in
``filp_bach4popper/popper-core`` and ``filp_bach4popper/bach``. To use another
copy of Popper, set FILP_POPPER_PATH (folder containing the ``popper`` package).
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = PACKAGE_DIR.parent          # the folder that contains filp_bach4popper/
DATASETS_DIR = PACKAGE_ROOT / "datasets"
BACH_DIR = PACKAGE_DIR / "bach"

# Time (seconds) allowed to a client to evaluate one program on its examples.
EVAL_TIMEOUT = "0.1"


def popper_path() -> Path:
    return Path(os.environ.get("FILP_POPPER_PATH", PACKAGE_DIR / "popper-core"))


def child_environment() -> dict[str, str]:
    """Environment of the store / server / client / centralized processes."""
    env = os.environ.copy()
    paths = [str(popper_path()), str(PACKAGE_ROOT)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONHASHSEED"] = "0"            # same hash order in every process
    env.setdefault("FILP_EVAL_TIMEOUT", EVAL_TIMEOUT)
    return env
