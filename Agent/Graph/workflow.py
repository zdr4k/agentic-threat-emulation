from uuid import uuid4

from langgraph.graph import StateGraph, START, END

from Graph.state import AgentState
from Graph.nodes import read_rule_node, display_rule_node


def build_graph():

    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("read_rule", read_rule_node)
    builder.add_node("display_rule", display_rule_node)

    # Define execution flow
    builder.add_edge(START, "read_rule")
    builder.add_edge("read_rule", "display_rule")
    builder.add_edge("display_rule", END)

    return builder.compile()


if __name__ == "__main__":

    graph = build_graph()

    initial_state = {
        "run_id": str(uuid4()),
        "rule_file": "powershell_encoded_command.yml",
        "status": "pending"
    }

    result = graph.invoke(initial_state)

    print(f"\nFinal status: {result['status']}")

    print(graph.get_graph().draw_mermaid())