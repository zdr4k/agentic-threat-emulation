
import asyncio
from uuid import uuid4

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from Graph.nodes import check_telemetry_node
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
    analyze_telemetry_node,
    display_report_node,
)

from Graph.persistence import (
    DATA_DIR,
    save_run,
    utc_now,
)
def route_candidates(state: AgentState) -> str:
    return "select" if state.get("atomic_candidates") else "empty"


def route_execution_mode(state: AgentState) -> str:
    mode = state.get("execution_mode", "autonomous")

    if mode not in ("autonomous", "manual"):
        raise ValueError(f"Unsupported execution mode: {mode}")

    return mode


def no_candidates_node(state: AgentState) -> dict:
    print("\nNo Atomic Tests found.")
    return {"status": "no_candidates"}

def route_approval(state: AgentState) -> str:
    return "approved" if state.get("approved") else "rejected"

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
            "empty": "no_candidates"
        }
    )

    builder.add_edge("select_atomic", "display_selection")

    builder.add_conditional_edges(
        "display_selection",
        route_execution_mode,
        {
            "autonomous": "autonomous_approval",
            "manual": "manual_approval"
        }
    )

    builder.add_edge(
        "autonomous_approval",
        "check_telemetry"
    )

    builder.add_conditional_edges(
        "manual_approval",
        route_approval,
        {
            "approved": "check_telemetry",
            "rejected": END,
        }
    )


    builder.add_edge(
        "check_telemetry",
        "analyze_telemetry"
    )

    builder.add_edge(
        "analyze_telemetry",
        "display_report"
    )

    builder.add_edge(
        "display_report",
        END
    )



    builder.add_edge("no_candidates", END)

    return builder.compile(checkpointer=checkpointer)



async def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    execution_mode = "autonomous"

    run_id = str(uuid4())

    config = {
        "configurable": {
            "thread_id": run_id,
        }
    }

    initial_state = {
        "run_id": run_id,
        "rule_file": "powershell_encoded_command.yml",
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

        if "__interrupt__" in result:
            print("\n[HITL] Human approval required.")

            decision = input(
                "Approve recommendation? (y/n): "
            ).strip().lower()

            result = await graph.ainvoke(
                Command(resume={
                    "approved": decision == "y",
                    "reason": (
                        "Approved via CLI"
                        if decision == "y"
                        else "Rejected via CLI"
                    ),
                }),
                config=config,
            )

        final_status = result["status"]

        # Persist the final timestamp in LangGraph state.
        await graph.aupdate_state(
            config,
            {"finished_at": utc_now()},
        )

        final_state = await graph.aget_state(config)
        state = final_state.values

        report_path = save_run(state)

        print(f"\nFinal status: {final_status}")
        print(f"Approved: {state.get('approved', False)}")
        print(f"Approval status: {state.get('approval_status')}")
        print(f"Run ID: {run_id}")
        print(f"Report: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())