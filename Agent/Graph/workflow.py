
import asyncio
from uuid import uuid4

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from Graph.state import AgentState
from Graph.nodes import (
    read_rule_node,
    resolve_technique_node,
    query_atomics_node,
    select_atomic_node,
    display_selection_node,
    autonomous_approval_node,
    manual_approval_node,
    check_telemetry_node,
    analyze_telemetry_node,
    display_report_node,
)
from Graph.persistence import DATA_DIR, save_run, utc_now


def route_candidates(state: AgentState) -> str:
    return "select" if state.get("atomic_candidates") else "empty"

def route_selected_atomic(state: AgentState) -> str:
    return "selected" if state.get("selected_atomic") else "none"


def route_execution_mode(state: AgentState) -> str:
    mode = state.get("execution_mode", "manual")

    if mode not in ("autonomous", "manual"):
        raise ValueError(f"Unsupported execution mode: {mode}")

    return mode


def route_approval(state: AgentState) -> str:
    return "approved" if state.get("approved") else "rejected"


def no_candidates_node(state: AgentState) -> dict:
    print("\nNo Atomic Tests found.")
    return {"status": "no_candidates"}


def build_graph(checkpointer):
    builder = StateGraph(AgentState)

    builder.add_node("read_rule", read_rule_node)
    builder.add_node("resolve_technique", resolve_technique_node)
    builder.add_node("query_atomics", query_atomics_node)
    builder.add_node("select_atomic", select_atomic_node)
    builder.add_node("display_selection", display_selection_node)
    builder.add_node("autonomous_approval", autonomous_approval_node)
    builder.add_node("manual_approval", manual_approval_node)
    builder.add_node("no_candidates", no_candidates_node)
    builder.add_node("check_telemetry", check_telemetry_node)
    builder.add_node("analyze_telemetry", analyze_telemetry_node)
    builder.add_node("display_report", display_report_node)

    builder.add_edge(START, "read_rule")
    builder.add_edge("read_rule", "resolve_technique")
    builder.add_edge("resolve_technique", "query_atomics")

    builder.add_conditional_edges(
        "query_atomics",
        route_candidates,
        {
            "select": "select_atomic",
            "empty": "no_candidates",
        },
    )
    
    builder.add_conditional_edges(
        "select_atomic",
        route_selected_atomic,
        {
            "selected": "display_selection",
            "none": END,
        },
    )


    builder.add_conditional_edges(
        "display_selection",
        route_execution_mode,
        {
            "autonomous": "autonomous_approval",
            "manual": "manual_approval",
        },
    )

    builder.add_edge("autonomous_approval", "check_telemetry")

    builder.add_conditional_edges(
        "manual_approval",
        route_approval,
        {
            "approved": "check_telemetry",
            "rejected": END,
        },
    )

    builder.add_edge("check_telemetry", "analyze_telemetry")
    builder.add_edge("analyze_telemetry", "display_report")
    builder.add_edge("display_report", END)
    builder.add_edge("no_candidates", END)

    return builder.compile(checkpointer=checkpointer)


async def run_validation(
    rule_file: str,
    execution_mode: str = "manual",
) -> dict:
    if not rule_file.strip():
        raise ValueError("A detection rule filename is required.")

    if execution_mode not in ("manual", "autonomous"):
        raise ValueError("Invalid execution mode.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid4())

    config = {
        "configurable": {
            "thread_id": run_id,
        }
    }

    initial_state = {
        "run_id": run_id,
        "rule_file": rule_file,
        "execution_mode": execution_mode,
        "started_at": utc_now(),
        "status": "pending",
    }

    checkpoint_path = DATA_DIR / "checkpoints.db"

    async with AsyncSqliteSaver.from_conn_string(
        str(checkpoint_path)
    ) as checkpointer:

        graph = build_graph(checkpointer)

        result = await graph.ainvoke(
            initial_state,
            config=config,
        )

        while "__interrupt__" in result:
            print("\n[HITL] Analyst approval required.")

            decision = input(
                "Approve recommendation? (y/N): "
            ).strip().lower()

            approved = decision == "y"

            result = await graph.ainvoke(
                Command(
                    resume={
                        "approved": approved,
                        "reason": (
                            "Approved via CLI"
                            if approved
                            else "Rejected via CLI"
                        ),
                    }
                ),
                config=config,
            )

        snapshot = await graph.aget_state(config)
        state = dict(snapshot.values)

        final_status = state.get("status", "completed")

        if state.get("approved") is False:
            final_status = "rejected"
        elif final_status == "pending":
            final_status = "completed"

        await graph.aupdate_state(
            config,
            {
                "finished_at": utc_now(),
                "status": final_status,
            },
        )

        snapshot = await graph.aget_state(config)
        state = dict(snapshot.values)

        report_path = save_run(state)

        print("\n=== VALIDATION SUMMARY ===")
        print("Rule:", state.get("rule_file"))
        print("Status:", state.get("status"))
        print("Approval:", state.get("approval_status"))
        print("Run ID:", run_id)
        print("Report:", report_path)

        return state


async def main():
    await run_validation(
        rule_file="powershell_encoded_command.yml",
        execution_mode="manual",
    )


if __name__ == "__main__":
    asyncio.run(main())
