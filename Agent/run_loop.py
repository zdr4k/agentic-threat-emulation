"""
run_loop.py: the full loop, end to end (Opção A, no approval gate yet).

  read the rule -> query atomics -> LLM picks one -> execute it -> wait for
  telemetry -> verdict (detected / gap / blind).

Deterministic orchestration for the parts that must be reliable (the execution
window, the verdict). The LLM only decides which atomic matches the rule.

Run (from the Agent folder):
  python run_loop.py
Needs in .env: OPENAI_API_KEY, SENTINEL_WORKSPACE_ID, MCP_URL, MCP_AUTH_TOKEN
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from Tools.read_rule import read_rule
from Tools.check_telemetry import check_telemetry_logic
from Clients.mcp import load_mcp_tools

load_dotenv()

RULE_FILE = "powershell_encoded_command.yml"
HOST = "ai-purple-vm"
# How the sub-technique is chosen. The rule maps to T1059; the PowerShell
# atomics live under T1059.001.
SUBTECHNIQUE = "T1059.001"

# Telemetry ingestion via AMA is not instant. Poll the verdict for a while.
POLL_SECONDS = 30
POLL_MAX_MINUTES = 12


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def pick_atomic(rule: dict, atomics_json: str) -> str:
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
            f"Here are candidate atomics for {SUBTECHNIQUE}:\n{atomics_json}\n\n"
            "Pick the one whose command would make this rule fire. "
            "Reply with only its auto_generated_guid."
        )),
    ])
    return msg.content.strip().strip('"').strip("'")


async def main():
    # 1. Read the rule.
    rule = read_rule.invoke({"file_name": RULE_FILE})
    print(f"[1] rule: {rule['display_name']}")
    print(f"    technique {rule['primary_technique']}, table {rule['table']}")

    # 2. Connect to the MCP and get its tools.
    mcp = {t.name: t for t in await load_mcp_tools()}

    # 3. Query atomics for the sub-technique.
    atomics = await mcp["query_atomics"].ainvoke(
        {"query": "powershell encoded command", "technique_id": SUBTECHNIQUE}
    )
    atomics_str = atomics if isinstance(atomics, str) else json.dumps(atomics)
    print(f"[2] queried atomics for {SUBTECHNIQUE}")

    # 4. LLM picks the matching atomic (the judgment step).
    guid = await pick_atomic(rule, atomics_str)
    print(f"[3] agent picked atomic {guid}")

    # 5. Execute it, recording the window. Cleanup runs automatically.
    start = utcnow_iso()
    print(f"[4] executing at {start} ...")
    result = await mcp["execute_atomic"].ainvoke({"auto_generated_guid": guid})
    end = utcnow_iso()
    print(f"    executed, finished {end}")

    # Pad the window slightly for clock skew.
    s = (datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
         - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    e = (datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")
         + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 6. Poll the verdict while telemetry ingests.
    print(f"[5] waiting for telemetry, window {s} .. {e}")
    deadline = time.time() + POLL_MAX_MINUTES * 60
    verdict = None
    while time.time() < deadline:
        verdict = check_telemetry_logic(
            table=rule["table"], rule_query=rule["query"],
            host=HOST, start_iso=s, end_iso=e,
        )
        if verdict["verdict"] != "blind":
            break  # telemetry arrived; verdict is meaningful
        print(f"    still blind (no telemetry yet), retry in {POLL_SECONDS}s")
        time.sleep(POLL_SECONDS)

    print("\n=== VERDICT ===")
    for k, v in verdict.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())