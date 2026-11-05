
from datetime import datetime, timedelta, timezone

from Clients.sentinel import SentinelClient


def query_rule_telemetry(
    rule: dict,
    timespan_hours: int = 24,
    client: SentinelClient | None = None,
) -> dict:
    """Query historical telemetry and return structured evidence."""

    client = client or SentinelClient()

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=timespan_hours)

    rows = client.query(
        kql=rule["query"],
        timespan_hours=timespan_hours,
    )

    event_count = len(rows)

    return {
        "telemetry_status": (
            "events_found" if event_count else "no_matches"
        ),
        "event_count": event_count,
        "sample_events": rows[:5],
        "timespan_hours": timespan_hours,
        "telemetry_evidence": {
            "query": rule["query"],
            "table": rule.get("table"),
            "window_start": start_time.isoformat(),
            "window_end": end_time.isoformat(),
            "returned_rows": event_count,
            "sample_size": min(event_count, 5),
            "source": "Microsoft Sentinel / Log Analytics",
            "validation_type": "historical_query",
        },
    }
