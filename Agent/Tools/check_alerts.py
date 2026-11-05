
# Tools/check_alerts.py

from __future__ import annotations

from datetime import timedelta

from Clients.sentinel import SentinelClient
from Tools.execution_evidence import parse_timestamp


def check_execution_alerts(
    execution: dict,
    *,
    delay_minutes: int = 30,
    max_results: int = 100,
    client: SentinelClient | None = None,
) -> dict:
    """Check Sentinel SecurityAlert records for a lab host."""

    if not 0 <= delay_minutes <= 1440:
        raise ValueError("delay_minutes must be between 0 and 1440")

    if not 1 <= max_results <= 1000:
        raise ValueError("max_results must be between 1 and 1000")

    client = client or SentinelClient()

    start = parse_timestamp(execution["started_at"])
    end = parse_timestamp(execution["finished_at"])

    window_start = start - timedelta(minutes=5)
    window_end = end + timedelta(minutes=delay_minutes)

    host = execution["host"]

    # Encode as a KQL string literal.
    host_literal = (
        host.replace("\\", "\\\\")
        .replace('"', '\\"')
    )

    kql = f"""
SecurityAlert
| where TimeGenerated between (
    datetime({window_start.strftime('%Y-%m-%dT%H:%M:%SZ')})
    ..
    datetime({window_end.strftime('%Y-%m-%dT%H:%M:%SZ')})
)
| where CompromisedEntity =~ "{host_literal}"
| project
    TimeGenerated,
    SystemAlertId,
    AlertName,
    AlertSeverity,
    ProviderName,
    ProductName,
    CompromisedEntity
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
        "host": host,
        "alert_status": (
            "candidate_alerts_found" if rows else "no_matches"
        ),
        "alert_count": len(rows),
        "alerts": rows,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "query": kql,
        "correlation_method": "host_and_time_window",
        "limitations": [
            "Matching host and time does not prove that an alert was caused by the test.",
            "Alerts without a matching CompromisedEntity may be missed.",
            "The query does not establish that an alert came from the target analytics rule.",
            "The result set is capped by max_results.",
        ],
    }
