
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "agent.db"
REPORT_DIR = DATA_DIR / "reports"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                rule_file TEXT,
                execution_mode TEXT,
                approval_status TEXT,
                status TEXT NOT NULL,
                assessment TEXT,
                report_path TEXT
            )
        """)


def save_run(state: dict) -> Path:
    """Persist a completed workflow and export its JSON report."""

    initialize_storage()

    run_id = state["run_id"]
    report_path = REPORT_DIR / f"{run_id}.json"

    report = {
        "run_id": run_id,
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "rule_file": state.get("rule_file"),
        "rule_name": state.get("rule", {}).get("display_name"),
        "technique_id": state.get("technique_id"),
        "selected_atomic": state.get("selected_atomic"),
        "selection_reason": state.get("selection_reason"),
        "execution_mode": state.get("execution_mode"),
        "approved": state.get("approved"),
        "approval_status": state.get("approval_status"),
        "approval_reason": state.get("approval_reason"),
        "telemetry_status": state.get("telemetry_status"),
        "event_count": state.get("event_count"),
        "telemetry_evidence": state.get("telemetry_evidence"),
        "telemetry_analysis": state.get("telemetry_analysis"),
        "status": state.get("status"),
    }

    report_path.write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO runs (
                run_id, started_at, finished_at,
                rule_file, execution_mode, approval_status,
                status, assessment, report_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                finished_at = excluded.finished_at,
                approval_status = excluded.approval_status,
                status = excluded.status,
                assessment = excluded.assessment,
                report_path = excluded.report_path
        """, (
            run_id,
            state.get("started_at") or utc_now(),
            state.get("finished_at"),
            state.get("rule_file"),
            state.get("execution_mode"),
            state.get("approval_status"),
            state.get("status", "unknown"),
            state.get("telemetry_analysis", {}).get("assessment"),
            str(report_path),
        ))

    return report_path


def list_runs(limit: int = 10) -> list[dict]:
    initialize_storage()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT
                run_id,
                started_at,
                finished_at,
                rule_file,
                execution_mode,
                approval_status,
                status,
                assessment
            FROM runs
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]
