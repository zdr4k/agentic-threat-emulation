
# test_validation.py

from Tools.execution_evidence import build_execution_evidence
from Tools.correlate_telemetry import correlate_telemetry
from Tools.check_alerts import check_execution_alerts
from Graph.detection_assessment import assess_detection
from dotenv import load_dotenv

# Load .env from the Agent directory
load_dotenv()


def main():
    # Replace with metadata from an actual authorized lab run.
    execution = build_execution_evidence(
        execution_id="lab-run-001",
        host="lab-win11-01",
        started_at="2026-11-04T06:00:00Z",
        finished_at="2026-11-04T06:02:00Z",
        status="completed",
        technique_id="T1059.001",
    )

    telemetry = correlate_telemetry(
        execution,
        table="DeviceProcessEvents",
    )

    alerts = check_execution_alerts(
        execution,
        delay_minutes=30,
    )

    assessment = assess_detection(
        execution,
        telemetry,
        alerts,
    )

    print("\n=== VALIDATION RESULTS ===")
    print("Execution:", execution["execution_id"])
    print("Telemetry:", telemetry["telemetry_status"])
    print("Events:", telemetry["returned_rows"])
    print("Alerts:", alerts["alert_status"])
    print("Alert count:", alerts["alert_count"])
    print("Assessment:", assessment["assessment"])
    print("Reason:", assessment["reason"])


if __name__ == "__main__":
    main()
