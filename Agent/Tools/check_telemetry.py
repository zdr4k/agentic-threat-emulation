"""
check_telemetry: decides detected / gap / blind after an atomic runs.

Two checks against the execution window, in order:
  Q1  any telemetry in the rule's table for this host?   no -> blind
  Q2  did the rule's query return rows?                   no -> gap, yes -> detected

Deterministic. The window (start, end) is passed in.
"""

from __future__ import annotations

import re

from langchain_core.tools import tool

from Clients.sentinel import SentinelClient

DETECTED = "detected"
GAP = "gap"
BLIND = "blind"

# Strip the rule's own scheduling filter (| where TimeGenerated > ago(...)) so
# the execution window is the only time bound applied.
_AGO_LINE = re.compile(
    r"(?im)^\s*\|\s*where\s+TimeGenerated\s*>\s*ago\([^)]*\)\s*$"
)


def _strip_ago(query: str) -> str:
    return _AGO_LINE.sub("", query)


def _presence_query(table: str, host: str, start_iso: str, end_iso: str) -> str:
    # Host column name differs by table.
    host_col = "DeviceName" if table in ("DeviceProcessEvents",
                                         "DeviceNetworkEvents",
                                         "DeviceFileEvents") else "Computer"
    return f"""
{table}
| where TimeGenerated between (datetime({start_iso}) .. datetime({end_iso}))
| where {host_col} == "{host}"
| count
""".strip()


def _rule_fired_query(rule_query: str, start_iso: str, end_iso: str) -> str:
    return f"""
{_strip_ago(rule_query)}
| where TimeGenerated between (datetime({start_iso}) .. datetime({end_iso}))
| count
""".strip()


def check_telemetry_logic(
    table: str,
    rule_query: str,
    host: str,
    start_iso: str,
    end_iso: str,
    client: SentinelClient | None = None,
) -> dict:
    """Verdict logic without the tool wrapper, so it can be unit tested."""
    client = client or SentinelClient()

    seen = client.count(_presence_query(table, host, start_iso, end_iso))
    if seen == 0:
        return {
            "verdict": BLIND,
            "telemetry_rows": 0,
            "rule_hits": 0,
            "reason": f"No telemetry in {table} for {host} in the window.",
        }

    hits = client.count(_rule_fired_query(rule_query, start_iso, end_iso))
    if hits == 0:
        return {
            "verdict": GAP,
            "telemetry_rows": seen,
            "rule_hits": 0,
            "reason": f"Telemetry present ({seen} rows), rule did not fire.",
        }

    return {
        "verdict": DETECTED,
        "telemetry_rows": seen,
        "rule_hits": hits,
        "reason": f"Telemetry present, rule fired ({hits} hits).",
    }


@tool
def check_telemetry(
    table: str,
    rule_query: str,
    host: str,
    start_iso: str,
    end_iso: str,
) -> dict:
    """Check whether a detection rule caught an emulated technique.

    Given the rule's source table and query, the target host, and the atomic's
    execution window (start_iso, end_iso, ISO 8601), returns a verdict:
    "blind" (no telemetry in the table for this host and window), "gap"
    (telemetry present but the rule did not fire), or "detected" (telemetry
    present and the rule fired). Use after running the atomic.
    """
    return check_telemetry_logic(table, rule_query, host, start_iso, end_iso)
