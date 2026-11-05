
from typing import TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    rule_file: str
    rule: dict
    status: str
    technique_id: str
    atomic_candidates: list[dict]
    selected_atomic: dict
    selection_reason: str
    execution_mode: str
    approved: bool
    approval_reason: str
    telemetry_status: str
    event_count: int
    sample_events: list[dict]
    timespan_hours: int
    telemetry_error: str
    telemetry_analysis: dict
    telemetry_evidence: dict
    approval_status: str
    started_at: str
    finished_at: str