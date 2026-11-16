"""Replay PR #55's invented worlds with the shipped DFL candidate for issue #62.

Uses the same fixed-weight context as solution.a_dfl's entry point. No training,
real-data path, configuration override or reserved evaluation is accepted.
Software success and football acceptance remain separate: --check exits 1 for
unmet targets or symmetry flags. Existing report files are never overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from solution.a_dfl import __version__
from solution.a_dfl.model import installed
from tools import football_acceptance as fa


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("The report destination must be new")

    root = Path(__file__).resolve().parents[1]
    paths = [Path(__file__), root / "configs/candidate_a_dfl.json"]
    paths += sorted((root / "solution/a_dfl").glob("*.py"))
    files = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in paths}
    rows = []
    with installed() as model:
        training = model["training"]
        for base in fa.scenarios():
            reference = None
            for mirror, offset, permute in ((False, 0, False), (True, 0, False),
                                             (False, 17, False), (False, 0, True)):
                case = fa.transform(base, mirror=mirror, offset=offset, permute=permute)
                predicted, technical = fa.run_a(case)
                row = fa.assess(case, predicted)
                aligned = predicted[offset:]
                if mirror:
                    aligned = np.where(aligned == "H", "A", np.where(aligned == "A", "H", aligned))
                if reference is None:
                    reference = aligned.copy()
                row["equivariance_mismatches"] = int(np.sum(aligned != reference))
                row.update(technical)
                rows.append(row)

    counts = {status: sum(row["status"] == status for row in rows)
              for status in ("pass", "fail", "diagnostic")}
    counts["invariance_failures"] = sum(row["equivariance_mismatches"] > 0 for row in rows)
    report = {
        "scope": "existing public synthetic development worlds; no new independent validation",
        "model": "candidate_a_dfl", "version": __version__, "training": training,
        "fixture_version": fa.VERSION, "identity": fa.source_identity(),
        "candidate_files_sha256": files, "p2_enabled": bool(fa.a_config.build()["p2.enabled"]),
        "counts": counts, "rows": rows,
        "limitations": [
            "Compact timeline and invented collective movement do not establish match accuracy.",
            "Diagnostic cases are not passes; this report does not select or tune a model.",
            "No challenge ground truth, video or reserved DFL match is opened.",
            "This is not independent clean-clone reproduction of the final submission.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print("Fixed DFL candidate synthetic development: " + json.dumps(counts, sort_keys=True))
    print("Report written; unchanged acceptance targets, weights and model configuration.")
    return 1 if args.check and (counts["fail"] or counts["invariance_failures"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
