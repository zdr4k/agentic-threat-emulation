
# Tools/execution_evidence.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp and normalize it to UTC."""
    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        raise ValueError(
            "Timestamp must include timezone information"
        )

    return parsed.astimezone(timezone.utc)


def build_execution_evidence(
    *,
    execution_id: str,
    host: str,
    started_at: str,
    finished_at: str,
    status: str,
    technique_id: str | None = None,
    atomic_guid: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict:
    """Normalize evidence from an authorized lab execution."""

    if not execution_id.strip():
        raise ValueError("execution_id is required")

    if not host.strip():
        raise ValueError("host is required")

    valid_statuses = {
        "completed",
        "failed",
        "cancelled",
    }

    if status not in valid_statuses:
        raise ValueError(
            f"Unsupported execution status: {status}"
        )

    start = parse_timestamp(started_at)
    end = parse_timestamp(finished_at)

    if end < start:
        raise ValueError(
            "finished_at cannot be earlier than started_at"
        )

    if end > datetime.now(timezone.utc):
        raise ValueError(
            "finished_at cannot be in the future"
        )

    if atomic_guid:
        UUID(atomic_guid)

    return {
        "execution_id": execution_id,
        "host": host,
        "started_at": start.isoformat(),
        "finished_at": end.isoformat(),
        "status": status,
        "technique_id": technique_id,
        "atomic_guid": atomic_guid,
        "metadata": metadata or {},
        "evidence_source": "external_execution_record",
    }
