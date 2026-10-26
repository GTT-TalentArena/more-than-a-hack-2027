"""What makes two held-out runs the same experiment, so a cached result is never reused for new code.

A run is identified by (match, profile, seed, model name) **and** two hashes:

- model identity: the config file plus every source file the model runs (its package for module
  models; the shared solution/ and starter code otherwise), P0 (solution/predict.py,
  solution/contract.py) and games.py;
- harness identity: heldout/ (conversion, degradation, bundles, scoring), the official metric code
  and the numerical environment (Python, numpy, pandas versions).

Change any of them and the run is recomputed and recorded separately; old results stay in
results.jsonl but no longer match.
"""

import hashlib
import json
import os
import platform

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = ("games.py", "solution/__init__.py", "solution/predict.py", "solution/contract.py")
HARNESS = ("heldout/convert.py", "heldout/degrade.py", "heldout/bundle.py", "heldout/score.py",
           "heldout/run.py", "heldout/identity.py", "evaluation/possession_metrics.py")


def _python_files(folder):
    found = []
    for base, dirs, files in os.walk(os.path.join(ROOT, folder)):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        found += [os.path.relpath(os.path.join(base, f), ROOT) for f in sorted(files) if f.endswith(".py")]
    return found


def files_hash(relpaths, extra=()):
    digest = hashlib.sha256()
    for rel in sorted(set(relpaths)):
        digest.update(rel.encode() + b"\0")
        with open(os.path.join(ROOT, rel), "rb") as handle:
            digest.update(handle.read())
        digest.update(b"\0")
    for item in extra:
        digest.update(str(item).encode() + b"\0")
    return digest.hexdigest()


def model_files(config):
    """Source files a P0 config runs, relative to the repository root."""
    with open(os.path.join(ROOT, config), encoding="utf-8-sig") as handle:
        spec = json.load(handle)
    if spec.get("model") == "module":
        package = spec["parameters"]["module"].split(".")
        return _python_files(os.path.join(*package)) + list(SHARED)
    top = [f for f in _python_files("solution") if f.count("/") == 1]
    return top + ["starter/baseline.py"] + list(SHARED)


def model_identity(config):
    return files_hash(model_files(config) + [config])


def environment():
    import pandas
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pandas.__version__}


def harness_identity():
    env = environment()
    return files_hash(HARNESS, extra=sorted(env.items()))
