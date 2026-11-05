"""Agentic Detection Validation — interactive CLI.

Run from the Agent folder: python main.py
Requires: OPENAI_API_KEY, SENTINEL_WORKSPACE_ID, MCP_URL, MCP_AUTH_TOKEN
Optional: ISSUE_REPO, ISSUE_TOKEN
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from workflow import run_validation
from persistence import list_runs
from Tools.select_rule import select_detection_rule


BANNER = r"""
           .         *          .
      *         .          *

     ___   ___   ___ _   _ ___
    / _ \ | _ \ / __| | | / __|
   / /_\ \|   /| (_ | |_| \__ \
  /_/   \_\_|_\ \___|\___/|___/

       AGENTIC DETECTION VALIDATION

       LangChain · MCP · Sentinel
                 v0.1
"""


def clear_screen():
    """Clear the terminal on Windows, macOS, and Linux."""
    if sys.stdout.isatty():
        os.system("cls" if os.name == "nt" else "clear")


def show_banner():
    print(BANNER)
    print("  " + "─" * 44)


def show_menu():
    print("  [1] Validate a specific detection rule")
    print("  [2] Let the AI Agent select a rule")
    print("  [3] View validation history")
    print("  [4] Exit")
    print("  " + "─" * 44)


def validate_specific_rule():
    rule_file = input("\n  Detection rule filename: ").strip()
    if not rule_file:
        print("\n  [!] Rule filename cannot be empty.")
        return

    print(f"\n  [+] Selected rule: {rule_file}")
    print("  [+] Starting validation workflow...\n")
    asyncio.run(run_validation(rule_file=rule_file, execution_mode="manual"))


def validate_ai_selected_rule():
    print("\n  [+] Fetching detection rules from GitHub...")
    print("  [+] AI Agent selecting a rule...")

    selection = select_detection_rule()
    print("\n  === AI RULE SELECTION ===")
    print(f"  Rule: {selection['filename']}")
    print(f"  Reason: {selection['reason']}")

    decision = input("\n  Validate this rule? (y/N): ").strip().lower()
    if decision != "y":
        print("\n  [!] Validation cancelled.")
        return

    asyncio.run(
        run_validation(rule_file=selection["filename"], execution_mode="manual")
    )


def show_history():
    runs = list_runs(limit=10)
    if not runs:
        print("\n  No validation history found.")
        return

    print("\n  === VALIDATION HISTORY ===\n")
    for index, run in enumerate(runs, start=1):
        print(f"  [{index}] {run['rule_file']}")
        print(f"      Run ID: {run['run_id']}")
        print(f"      Date: {run['started_at']}")
        print(f"      Status: {run['status']}")
        print(f"      Assessment: {run['assessment'] or 'N/A'}\n")


def main():
    while True:
        clear_screen()
        show_banner()
        show_menu()
        choice = input("\n  Select an option: ").strip()

        if choice == "4":
            print("\n  Exiting agent.\n")
            return

        try:
            if choice == "1":
                validate_specific_rule()
            elif choice == "2":
                validate_ai_selected_rule()
            elif choice == "3":
                show_history()
            else:
                print("\n  [!] Invalid option.")
        except KeyboardInterrupt:
            print("\n  [!] Operation interrupted.")
        except Exception as exc:
            print(f"\n  [ERROR] {type(exc).__name__}: {exc}")

        try:
            input("\n  Press Enter to return to the menu...")
        except (KeyboardInterrupt, EOFError):
            print()
            return


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n  Exiting agent.\n")
