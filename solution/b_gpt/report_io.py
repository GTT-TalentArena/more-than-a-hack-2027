"""Safe local CSV input and atomic aggregate JSON output."""

import csv
import json
import os
from pathlib import Path
import tempfile

import numpy as np
from .io import InputError


def read_labels(path, expected):
    labels = np.empty(expected, dtype="<U1")
    count = 0
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is None or [h.strip().lower() for h in header] != ["frame", "label"]:
                raise InputError("Prediction CSV must have frame,label columns.")
            for row in reader:
                if len(row) != 2 or count >= expected:
                    raise InputError("Invalid prediction record or row count; values suppressed.")
                if int(row[0]) != count:
                    raise InputError("Prediction frame indices must be consecutive from zero.")
                label = row[1].strip().upper()
                if label not in ("H", "A", "D", "X"):
                    raise InputError("Invalid prediction label; values suppressed.")
                labels[count] = label
                count += 1
    except InputError:
        raise
    except (OSError, ValueError, csv.Error, UnicodeError):
        raise InputError("Cannot read prediction CSV; input values suppressed.") from None
    if count != expected:
        raise InputError("Prediction row count does not match the tactical video length.")
    return labels


def write_summary(path, diagnostics, metadata=None):
    """Atomically write new run metadata; retain existing metadata in reports-only mode."""
    path = Path(path)
    report = {} if metadata is None else metadata.copy()
    try:
        if metadata is None and path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise InputError("Existing summary must be a JSON object.")
    except (OSError, ValueError, UnicodeError):
        raise InputError("Cannot read existing summary JSON; values suppressed.") from None
    report["full_match_diagnostics"] = diagnostics
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".diagnostics-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
