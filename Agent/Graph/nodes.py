
import json

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from Clients.mcp import load_mcp_tools
from Graph.state import AgentState
from Tools.read_rule import read_rule
from langgraph.types import interrupt
import asyncio
from Graph.telemetry_analysis import analyze_telemetry

from Tools.query_telemetry import query_rule_telemetry

# ---------------------------------------------------------
# 1. Read Detection Rule
# ---------------------------------------------------------

def read_rule_node(state: AgentState) -> dict:
    """Load a detection rule from GitHub."""

    rule = read_rule.invoke({
        "file_name": state["rule_file"]
    })

    return {
        "rule": rule,
        "status": "rule_loaded"
    }


# ---------------------------------------------------------
# 2. Resolve MITRE ATT&CK Technique
# ---------------------------------------------------------

class TechniqueSelection(BaseModel):
    technique_id: str = Field(
        description="MITRE ATT&CK technique or subtechnique ID"
    )
    reason: str = Field(
        description="Reason for choosing this technique"
    )


async def resolve_technique_node(state: AgentState) -> dict:
    """Identify the most relevant ATT&CK technique."""

    rule = state["rule"]

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0
    ).with_structured_output(TechniqueSelection)

    selection = await llm.ainvoke([
        (
            "system",
            "You are a MITRE ATT&CK mapping assistant. "
            "Identify the most specific ATT&CK technique or "
            "subtechnique supported by the detection rule. "
            "Do not invent technique IDs. "
            "If a more specific subtechnique is not justified, "
            "preserve the original technique ID."
        ),
        (
            "human",
            json.dumps({
                "rule_name": rule["display_name"],
                "original_technique": rule["primary_technique"],
                "rule_query": rule["query"]
            })
        )
    ])

    print(f"\n[MITRE] Original: {rule['primary_technique']}")
    print(f"[MITRE] Resolved: {selection.technique_id}")
    print(f"[MITRE] Reason: {selection.reason}")

    return {
        "technique_id": selection.technique_id,
        "status": "technique_resolved"
    }


# ---------------------------------------------------------
# 3. Parse MCP Response
# ---------------------------------------------------------

def parse_atomic_response(result) -> list[dict]:
    """Extract Atomic Tests from MCP content blocks."""

    if isinstance(result, str):
        result = json.loads(result)

    if isinstance(result, dict):
        return result.get("atomics", [])

    if isinstance(result, list):
        atomics = []

        for item in result:
            if not isinstance(item, dict):
                continue

            if item.get("type") != "text":
                continue

            payload = json.loads(item["text"])

            if not isinstance(payload, dict):
                raise ValueError("Unexpected MCP payload")

            atomics.extend(payload.get("atomics", []))

        return atomics

    raise ValueError(
        f"Unexpected MCP response type: {type(result)}"
    )


# ---------------------------------------------------------
# 4. Query Atomic Tests
# ---------------------------------------------------------


async def query_atomics_node(state: AgentState) -> dict:
    """Discover Atomic Tests through a persistent MCP session."""

    from Clients.mcp import mcp_session

    technique = state["technique_id"]
    rule = state["rule"]

    queries = [
        technique,
        rule["display_name"]
    ]

    candidates = []
    seen_guids = set()

    async with mcp_session() as tools:
        if "query_atomics" not in tools:
            raise RuntimeError("query_atomics tool not available")

        for query in queries:
            result = await tools["query_atomics"].ainvoke({
                "query": query,
                "technique_id": technique
            })

            found = parse_atomic_response(result)

            print(
                f"[MCP] Query: {query} | "
                f"Results: {len(found)}"
            )

            for atomic in found:
                guid = atomic.get("auto_generated_guid")

                if guid and guid not in seen_guids:
                    seen_guids.add(guid)
                    candidates.append(atomic)

    print(f"\n[MCP] Technique: {technique}")
    print(f"[MCP] Unique candidates: {len(candidates)}")

    return {
        "atomic_candidates": candidates,
        "status": "atomics_loaded"
    }


# ---------------------------------------------------------
# 5. Select Atomic Test with LLM
# ---------------------------------------------------------

class AtomicSelection(BaseModel):
    guid: str = Field(
        description="Selected Atomic Test GUID"
    )
    reason: str = Field(
        description="Why this test matches the detection rule"
    )



async def select_atomic_node(state: AgentState) -> dict:
    """Select an Atomic Test only when behavior matches the rule."""

    rule = state["rule"]
    candidates = state["atomic_candidates"]

    summaries = [
        {
            "guid": atomic.get("auto_generated_guid"),
            "name": atomic.get("name"),
            "description": atomic.get("description", ""),
            "supported_platforms": atomic.get("supported_platforms", []),
        }
        for atomic in candidates
    ]

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    ).with_structured_output(AtomicSelection)

    selection = await llm.ainvoke([
        (
            "system",
            """
You are a detection engineering validation assistant.

Your task is to determine whether an Atomic Test is
suitable for validating a specific detection rule.

Evaluate:
1. The actual behavior detected by the KQL query.
2. The behavior described in each Atomic Test.
3. Whether the test would plausibly generate the
   specific telemetry required by the rule.

Rules:
- MITRE technique similarity alone is insufficient.
- Prefer direct behavioral correspondence.
- Do not assume a test generates AzureActivity events
  simply because it involves Azure or Entra ID.
- If the metadata is insufficient, return guid=null.
- If no test is suitable, return guid=null.
- Never invent a GUID.
- Do not generate commands or execute tests.
"""
        ),
        (
            "human",
            json.dumps({
                "rule_name": rule["display_name"],
                "rule_query": rule["query"],
                "rule_table": rule.get("table"),
                "technique": state["technique_id"],
                "candidates": summaries,
            })
        ),
    ])

    if selection.guid is None:
        print("\n[Selection] No suitable Atomic Test found.")
        print(f"[Selection] Reason: {selection.reason}")

        return {
            "selected_atomic": {},
            "selection_reason": selection.reason,
            "status": "no_suitable_atomic",
        }


    # Normalize the LLM response.
    guid = selection.guid

    if isinstance(guid, str):
        guid = guid.strip()

        if guid.lower() in ("", "none", "null", "n/a"):
            guid = None

    # Verify the GUID against the actual MCP candidates.
    selected = next(
        (
            atomic for atomic in candidates
            if atomic.get("auto_generated_guid") == guid
        ),
        None,
    )

    if selected is None:
        print("\n[Selection] No valid Atomic Test selected.")
        print(f"[Selection] LLM returned: {guid!r}")
        print(f"[Selection] Reason: {selection.reason}")

        return {
            "selected_atomic": {},
            "selection_reason": (
                selection.reason
                if guid is None
                else "LLM returned a GUID not present in MCP candidates."
            ),
            "status": "no_suitable_atomic",
        }

    return {
        "selected_atomic": {
            "guid": selection.guid,
            "name": selected["name"],
        },
        "selection_reason": selection.reason,
        "status": "atomic_recommended",
    }

# ---------------------------------------------------------
# 6. Display Recommendation
# ---------------------------------------------------------

def display_selection_node(state: AgentState) -> dict:
    """Display the LLM recommendation."""

    selected = state["selected_atomic"]

    print(f"\nRecommended Test: {selected['name']}")
    print(f"GUID: {selected['guid']}")
    print(f"Reason: {state['selection_reason']}")

    return {"status": "completed"}


def autonomous_approval_node(state: AgentState) -> dict:
    selected = state["selected_atomic"]

    print(f"\n[AUTO] Recommendation accepted: {selected['name']}")

    return {
        "approved": True,
        "approval_status": "auto_approved",
        "approval_reason": "Accepted by autonomous workflow",
        "status": "approved",
    }


def manual_approval_node(state: AgentState) -> dict:
    selected = state["selected_atomic"]

    decision = interrupt({
        "type": "atomic_approval",
        "test_name": selected["name"],
        "guid": selected["guid"],
        "selection_reason": state["selection_reason"],
    })

    if not isinstance(decision, dict):
        raise ValueError("Approval decision must be a dictionary")

    approved = decision.get("approved")

    if not isinstance(approved, bool):
        raise ValueError("'approved' must be a boolean")

    return {
        "approved": approved,
        "approval_status": (
            "human_approved" if approved else "human_rejected"
        ),
        "approval_reason": decision.get(
            "reason",
            "Approved by human" if approved else "Rejected by human",
        ),
        "status": "approved" if approved else "rejected",
    }




async def check_telemetry_node(state: AgentState) -> dict:
    """Query historical Sentinel telemetry for the rule."""

    print("\n[Sentinel] Checking historical telemetry...")

    try:
        result = await asyncio.to_thread(
            query_rule_telemetry,
            rule=state["rule"],
            timespan_hours=24,
        )

        print(
            f"[Sentinel] Status: "
            f"{result['telemetry_status']}"
        )
        print(
            f"[Sentinel] Rows returned: "
            f"{result['event_count']}"
        )

        return {
            **result,
            "status": "telemetry_checked",
        }

    except Exception as exc:
        error_type = type(exc).__name__

        print(f"[Sentinel] Query failed: {error_type}")

        return {
            "telemetry_status": "query_error",
            "telemetry_error": error_type,
            "event_count": 0,
            "sample_events": [],
            "telemetry_evidence": {
                "source": "Microsoft Sentinel / Log Analytics",
                "validation_type": "historical_query",
                "query": state["rule"]["query"],
                "table": state["rule"].get("table"),
                "error_type": error_type,
            },
            "status": "telemetry_error",
        }



async def analyze_telemetry_node(state: AgentState) -> dict:
    """Generate an evidence-based telemetry assessment."""

    print("\n[Analysis] Analyzing Sentinel evidence...")

    try:
        analysis = await analyze_telemetry(state)

        print(f"[Analysis] Assessment: {analysis['assessment']}")
        print(f"[Analysis] Finding: {analysis['finding']}")

        return {
            "telemetry_analysis": analysis,
            "status": "analysis_completed",
        }

    except Exception as exc:
        print(f"[Analysis] Failed: {type(exc).__name__}")

        return {
            "telemetry_analysis": {
                "assessment": "inconclusive",
                "finding": "Telemetry analysis could not be completed.",
                "reasoning": "LLM analysis failed.",
                "limitations": [
                    "Automated interpretation unavailable."
                ],
            },
            "status": "analysis_error",
        }


def display_report_node(state: AgentState) -> dict:
    """Display the final detection assessment."""

    analysis = state["telemetry_analysis"]
    evidence = state.get("telemetry_evidence", {})

    print("\n========== DETECTION ASSESSMENT ==========")
    print(f"Rule: {state['rule']['display_name']}")
    print(f"Technique: {state['technique_id']}")
    print(f"Atomic: {state['selected_atomic']['name']}")
    print(f"Approved: {state.get('approved', False)}")
    print(f"Telemetry: {state.get('telemetry_status')}")
    print(f"Rows: {state.get('event_count', 0)}")

    if evidence:
        print(f"Window: {evidence.get('window_start')}")
        print(f"       → {evidence.get('window_end')}")

    print(f"\nAssessment: {analysis['assessment']}")
    print(f"Finding: {analysis['finding']}")
    print(f"Reasoning: {analysis['reasoning']}")

    for limitation in analysis.get("limitations", []):
        print(f"Limitation: {limitation}")

    print("==========================================")

    if state.get("status") == "analysis_error":
        return {"status": "analysis_error"}

    return {"status": "completed"}
