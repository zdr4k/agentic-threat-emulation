from uuid import uuid4

from Graph.state import AgentState
from Tools.read_rule import read_rule


def read_rule_node(state: AgentState) -> dict:
    """Load a detection rule using the existing tool."""

    rule = read_rule.invoke({
        "file_name": state["rule_file"]
    })

    return {
        "rule": rule,
        "status": "rule_loaded"
    }


def display_rule_node(state: AgentState) -> dict:
    """Display the rule information."""

    rule = state["rule"]

    print(f"\nRun ID: {state['run_id']}")
    print(f"Rule: {rule['display_name']}")
    print(f"Technique: {rule['primary_technique']}")
    print(f"Table: {rule['table']}")

    return {
        "status": "completed"
    }