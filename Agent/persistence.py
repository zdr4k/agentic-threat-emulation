"""
persistence.py: an append-only JSONL log of validation runs.

Lightweight on purpose: one JSON object per line, newest read from the tail.
Path is runs.jsonl next to this file (override with RUNS_FILE). Add it to
.gitignore; it is local run history, not source.
"""

from __future__ import annotations

import json
import os

RUNS_FILE = os.getenv(
    "RUNS_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs.jsonl"),
)


def save_run(record: dict) -> None:
    """Append one run record. Best effort: never breaks a run on an I/O error."""
    try:
        with open(RUNS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


def list_runs(limit: int = 10) -> list[dict]:
    """Return the last `limit` runs, newest first."""
    if not os.path.exists(RUNS_FILE):
        return []
    with open(RUNS_FILE, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip()]
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))
