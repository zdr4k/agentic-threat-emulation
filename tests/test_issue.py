"""
test_issue.py: verify the verdict-to-issue path without the lab.

  python tests/test_issue.py          offline checks only (no network)
  python tests/test_issue.py --live   also opens real gap + blind issues
                                       in ISSUE_REPO (needs GITHUB_TOKEN)

The offline checks prove the issue is built correctly for each verdict. The
live run proves the GitHub side (auth, create, idempotent re-open) end to end,
without needing Azure, the MCP, or the VM.
"""

import os
import sys

# tests/ sits at the repo root; the agent package is under Agent/.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "Agent"))

try:
    from dotenv import load_dotenv
    # pick up ISSUE_REPO / GITHUB_TOKEN for --live, from .env here or in Agent/
    load_dotenv()
    load_dotenv(os.path.join(_HERE, "..", "Agent", ".env"))
except ImportError:
    pass

from Clients.github import issue_for, report_verdict  # noqa: E402

RULE = {
    "display_name": "PowerShell encoded command execution",
    "primary_technique": "T1059",
    "table": "Event",
    "query": "Event | where ... | where CommandLine has_any (...)",
}
WINDOW = ("2026-11-01T08:00:00Z", "2026-11-01T08:10:00Z")
GUID = "1c0a870f-dc74-49cf-9afc-eccc45e58790"

GAP = {"verdict": "gap", "telemetry_rows": 3, "rule_hits": 0,
       "reason": "Telemetry present (3 rows), rule did not fire."}
BLIND = {"verdict": "blind", "telemetry_rows": 0, "rule_hits": 0,
         "reason": "No telemetry in Event for ai-purple-vm in the window."}
DETECTED = {"verdict": "detected", "telemetry_rows": 3, "rule_hits": 1,
            "reason": "Telemetry present, rule fired (1 hits)."}


def offline():
    # detected builds nothing
    assert issue_for(RULE, GUID, WINDOW, DETECTED) is None

    # gap and blind build distinct titles and labels
    gt, gb, gl = issue_for(RULE, GUID, WINDOW, GAP)
    assert "Coverage gap" in gt and gl == ["detection-gap"]
    assert "telemetry_rows: 3" in gb and GUID in gb

    bt, bb, bl = issue_for(RULE, GUID, WINDOW, BLIND)
    assert "Collection gap" in bt and bl == ["collection-gap"]
    assert gt != bt

    print("offline OK: detected -> none, gap -> detection-gap, blind -> collection-gap")


def live():
    if not os.getenv("ISSUE_REPO"):
        print("live skipped: set ISSUE_REPO and GITHUB_TOKEN")
        return
    print("gap  ->", report_verdict(RULE, GUID, WINDOW, GAP))
    print("gap  -> (re-run, should reuse)", report_verdict(RULE, GUID, WINDOW, GAP))
    print("blind->", report_verdict(RULE, GUID, WINDOW, BLIND))
    print("detected ->", report_verdict(RULE, GUID, WINDOW, DETECTED))  # None


if __name__ == "__main__":
    offline()
    if "--live" in sys.argv:
        live()