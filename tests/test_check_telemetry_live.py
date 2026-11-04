"""
test_check_telemetry_live.py

Runs check_telemetry against the real Sentinel workspace, over a wide window.

Prereqs (in the Codespace):
  pip install azure-identity azure-monitor-query langchain-core pyyaml python-dotenv
  az login
  .env with SENTINEL_WORKSPACE_ID=<workspace customer id>

Run (from the tests folder):
  python test_check_telemetry_live.py
"""

import os
import sys
import urllib.request

# Make the Agent folder importable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Agent"))

from dotenv import load_dotenv

from Tools.read_rule import parse_rule_text
from Tools.check_telemetry import check_telemetry_logic

load_dotenv()

# Wide window so time zone and the rule's internal ago() filter don't bite.
START = "2026-11-01T00:00:00Z"
END = "2026-11-01T23:59:59Z"
HOST = "ai-purple-vm"
RULE_FILE = "powershell_encoded_command.yml"


def main():
    url = ("https://raw.githubusercontent.com/zdr4k/DE-TH-Sentinel-DaC/"
           f"main/Rules/{RULE_FILE}")
    with urllib.request.urlopen(url) as r:
        rule = parse_rule_text(r.read().decode("utf-8"))

    print(f"rule:    {rule['display_name']}")
    print(f"table:   {rule['table']}")
    print(f"host:    {HOST}")
    print(f"window:  {START} .. {END}\n")

    result = check_telemetry_logic(
        table=rule["table"],
        rule_query=rule["query"],
        host=HOST,
        start_iso=START,
        end_iso=END,
    )

    print("=== VERDICT ===")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()