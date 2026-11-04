from typing import TypedDict
from uuid import uuid4


class AgentState(TypedDict, total=False):
    run_id: str
    rule_file: str
    rule: dict
    status: str