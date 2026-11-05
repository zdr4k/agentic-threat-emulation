
# Graph/detection_assessment.py

from __future__ import annotations


def assess_detection(
    execution: dict,
    telemetry: dict,
    alerts: dict,
    *,
    target_rule_alert_confirmed: bool = False,
    observation_complete: bool = False,
    telemetry_coverage_verified: bool = False,
) -> dict:
    """Evaluate a detection using recorded execution evidence."""

    execution_status = execution.get("status")
    telemetry_status = telemetry.get("telemetry_status")
    alert_status = alerts.get("alert_status")

    if execution_status != "completed":
        assessment = "inconclusive"
        reason = "The recorded execution did not complete successfully."

    elif target_rule_alert_confirmed:
        assessment = "detected"
        reason = (
            "An alert from the target detection rule was "
            "independently confirmed and correlated with the execution."
        )

    elif (
        observation_complete
        and telemetry_coverage_verified
        and telemetry_status == "events_found"
        and alert_status == "no_matches"
    ):
        assessment = "inconclusive"
        reason = (
            "Telemetry exists, but the current alert query does not "
            "establish complete coverage of the target detection rule."
        )

    else:
        assessment = "inconclusive"
        reason = (
            "Available evidence is insufficient to establish "
            "whether the target detection rule fired."
        )

    return {
        "execution_id": execution.get("execution_id"),
        "assessment": assessment,
        "reason": reason,
        "execution_status": execution_status,
        "telemetry_status": telemetry_status,
        "alert_status": alert_status,
        "target_rule_alert_confirmed": target_rule_alert_confirmed,
        "observation_complete": observation_complete,
        "telemetry_coverage_verified": telemetry_coverage_verified,
    }
