
# Tools/correlate_telemetry.py

from __future__ import annotations

from datetime import timedelta

from Clients.sentinel import SentinelClient
from Tools.execution_evidence import parse_timestamp


SUPPORTED_TABLES = {
    "DeviceProcessEvents": "DeviceName",
    "DeviceEvents": "DeviceName",
    "DeviceNetworkEvents": "DeviceName",
    "SecurityEvent": "Computer",
    "SysmonEvent": "Computer",
}


def correlate_telemetry(
    execution: dict,
    *,
    table: str = "DeviceProcessEvents",
    buffer_minutes: int = 5,
    max_results: int = 100,
    client: SentinelClient | None = None,
) -> dict:
    """Find Sentinel events associated with a recorded lab execution."""

    if table not in SUPPORTED_TABLES:
        raise ValueError(
            f"Unsupported telemetry table: {table}"
        )

    if buffer_minutes < 0:
        raise ValueError("buffer_minutes must be non-negative")

    if not 1 <= max_results <= 1000:
        raise ValueError("max_results must be between 1 and 1000")

    client = client or SentinelClient()

    start = parse_timestamp(execution["started_at"])
    end = parse_timestamp(execution["finished_at"])

    window_start = start - timedelta(minutes=buffer_minutes)
    window_end = end + timedelta(minutes=buffer_minutes)

    host_column = SUPPORTED_TABLES[table]

    # Safely encode the host as a KQL string literal.
    host_literal = (
        execution["host"]
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )

    start_literal = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_literal = window_end.strftime("%Y-%m-%dT%H:%M:%SZ")

    kql = f"""
{table}
| where TimeGenerated between (
    datetime({start_literal}) .. datetime({end_literal})
)
| where {host_column} =~ "{host_literal}"
| order by TimeGenerated asc
| take {max_results}
""".strip()


    rows = client.query_range(
        kql=kql,
        start=window_start,
        end=window_end,
    )


    return {
        "execution_id": execution["execution_id"],
        "host": execution["host"],
        "table": table,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "telemetry_status": (
            "events_found" if rows else "no_matches"
        ),
        "returned_rows": len(rows),
        "sample_events": rows[:10],
        "query": kql,
        "correlation_method": "host_and_time_window",
        "limitations": [
            "Host and time proximity do not prove that an event was caused by the test.",
            "The result count is limited by max_results.",
            "The selected table may not contain the telemetry required by the detection rule.",
        ],
    }
