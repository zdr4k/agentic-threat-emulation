"""
workflow.py: run one validation end to end for a given rule.

  read the rule -> search atomics for its technique -> LLM picks one ->
  (manual gate) execute it -> wait for telemetry -> verdict -> file an issue
  on a gap or a blind spot.

The technique is taken from the rule, not hardcoded. The LLM only picks which
atomic matches; the execution window and the verdict are deterministic code.
Every run is recorded via persistence.save_run.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from Tools.read_rule import read_rule
from Tools.check_telemetry import check_telemetry_logic
from Clients.mcp import load_mcp_tools
from Clients.github import report_verdict
from persistence import save_run

HOST = os.getenv("LAB_HOST", "ai-purple-vm")

# Telemetry ingestion via AMA is not instant. Poll the verdict for a while.
POLL_SECONDS = 30
POLL_MAX_MINUTES = 12

_SUBTECH = re.compile(r"^T\d{4}\.\d{3}$")
# Generic words in rule names that hurt the atomic text search (AND logic).
_STOP = {"execution", "activity", "suspicious", "detection", "detects",
         "detected", "via", "using", "with", "the", "a", "an", "and", "or"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_query(rule: dict) -> dict:
    """Build query_atomics args from the rule, not a hardcoded technique.

    The ART index matches technique_id exactly, so a base technique (T1059)
    has no atomics of its own: its tests live under sub-techniques (T1059.001).
    So pass technique_id only when the rule carries a sub-technique, and
    otherwise lean on a free-text query built from the rule name.
    """
    tech = rule.get("primary_technique") or ""
    words = [w for w in re.findall(r"[A-Za-z0-9]+", (rule.get("display_name") or "").lower())
             if w not in _STOP]
    args = {"query": " ".join(words) or "powershell"}
    if _SUBTECH.match(tech):
        args["technique_id"] = tech
    return args


async def _pick_atomic(rule: dict, atomics_json: str) -> str:
    """LLM picks the atomic GUID that matches what the rule detects."""
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    msg = model.invoke([
        SystemMessage(content=(
            "You pick the single atomic test that best exercises what a "
            "detection rule looks for. Reply with ONLY the atomic's "
            "auto_generated_guid, nothing else."
        )),
        HumanMessage(content=(
            f"The rule detects this (KQL):\n{rule['query']}\n\n"
            f"Candidate atomics:\n{atomics_json}\n\n"
            "Pick the one whose command would make this rule fire. "
            "Reply with only its auto_generated_guid."
        )),
    ])
    return msg.content.strip().strip('"').strip("'")


async def run_validation(rule_file: str, execution_mode: str = "manual"):
    """Validate one rule end to end. Returns the verdict dict (or None if the
    execution was cancelled at the manual gate)."""
    run_id = uuid.uuid4().hex[:12]
    started = _utcnow_iso()
    status, verdict = "failed", None
    try:
        # 1. Read the rule. The technique comes from here.
        rule = read_rule.invoke({"file_name": rule_file})
        print(f"[1] rule: {rule['display_name']}")
        print(f"    technique {rule['primary_technique']}, table {rule['table']}")

        # 2. Connect to the MCP and search atomics for the rule's technique.
        mcp = {t.name: t for t in await load_mcp_tools()}
        q = atomic_query(rule)
        atomics = await mcp["query_atomics"].ainvoke(q)
        atomics_str = atomics if isinstance(atomics, str) else json.dumps(atomics)
        print(f"[2] queried atomics ({q})")

        # 3. LLM picks the matching atomic (the only judgment step).
        guid = await _pick_atomic(rule, atomics_str)
        print(f"[3] agent picked atomic {guid}")

        # Manual gate: approve this specific atomic before it runs on the VM.
        if execution_mode == "manual":
            ok = input(f"    execute atomic {guid} on {HOST}? (y/N): ").strip().lower()
            if ok != "y":
                print("    execution cancelled")
                status = "cancelled"
                return None

        # 4. Execute it, recording the window. Cleanup runs automatically.
        start = _utcnow_iso()
        print(f"[4] executing at {start} ...")
        await mcp["execute_atomic"].ainvoke({"auto_generated_guid": guid})
        end = _utcnow_iso()
        print(f"    executed, finished {end}")

        # Pad the window slightly for clock skew.
        s = (datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
             - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        e = (datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")
             + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 5. Poll the verdict while telemetry ingests.
        print(f"[5] waiting for telemetry, window {s} .. {e}")
        deadline = time.time() + POLL_MAX_MINUTES * 60
        while time.time() < deadline:
            verdict = check_telemetry_logic(
                table=rule["table"], rule_query=rule["query"],
                host=HOST, start_iso=s, end_iso=e,
            )
            if verdict["verdict"] != "blind":
                break
            print(f"    still blind (no telemetry yet), retry in {POLL_SECONDS}s")
            time.sleep(POLL_SECONDS)

        print("\n=== VERDICT ===")
        for k, v in verdict.items():
            print(f"  {k}: {v}")

        # 6. Route the verdict: a gap or blind spot becomes a DaC issue.
        report_verdict(rule, guid, (s, e), verdict)
        status = "completed"
        return verdict
    finally:
        save_run({
            "run_id": run_id,
            "rule_file": rule_file,
            "started_at": started,
            "status": status,
            "assessment": (verdict or {}).get("verdict"),
        })
