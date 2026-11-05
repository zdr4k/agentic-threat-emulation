
import asyncio

from Graph.workflow import run_validation
from Graph.persistence import list_runs
from Tools.select_rule import select_detection_rule



def validate_ai_selected_rule():
    print("\n[+] Fetching detection rules from GitHub...")
    print("[+] AI Agent selecting a rule...")

    selection = select_detection_rule()

    print("\n=== AI RULE SELECTION ===")
    print("Rule:", selection["filename"])
    print("Reason:", selection["reason"])

    decision = input(
        "\nValidate this rule? (y/N): "
    ).strip().lower()

    if decision != "y":
        print("[!] Validation cancelled.")
        return

    asyncio.run(
        run_validation(
            rule_file=selection["filename"],
            execution_mode="manual",
        )
    )



def show_banner():
    print(r"""
╔══════════════════════════════════════════════╗
║                                              ║
║       AGENTIC DETECTION VALIDATION           ║
║                                              ║
║       LangGraph  ·  MCP  ·  Sentinel          ║
║                                              ║
║       AI-Powered Detection Engineering       ║
║                                        v0.1  ║
╚══════════════════════════════════════════════╝
""")

def show_menu():
    print("[1] Validate a specific detection rule")
    print("[2] Let the AI Agent select a rule")
    print("[3] View validation history")
    print("[4] Exit")


def validate_specific_rule():
    rule_file = input(
        "\nDetection rule filename: "
    ).strip()

    if not rule_file:
        print("[!] Rule filename cannot be empty.")
        return

    print(f"\n[+] Selected rule: {rule_file}")
    print("[+] Starting validation workflow...\n")

    asyncio.run(
        run_validation(
            rule_file=rule_file,
            execution_mode="manual",
        )
    )


def show_history():
    runs = list_runs(limit=10)

    if not runs:
        print("\nNo validation history found.")
        return

    print("\n=== VALIDATION HISTORY ===\n")

    for index, run in enumerate(runs, start=1):
        print(f"[{index}] {run['rule_file']}")
        print(f"    Run ID: {run['run_id']}")
        print(f"    Date: {run['started_at']}")
        print(f"    Status: {run['status']}")
        print(f"    Assessment: {run['assessment'] or 'N/A'}")
        print()


def main():
    while True:
        show_banner()
        show_menu()

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            try:
                validate_specific_rule()
            except Exception as exc:
                print(f"\n[ERROR] Validation failed: {exc}")

        elif choice == "2":
            try:
                validate_ai_selected_rule()
            except Exception as exc:
                print(f"\n[ERROR] AI selection failed: {exc}")

        elif choice == "3":
            try:
                show_history()
            except Exception as exc:
                print(f"\n[ERROR] Cannot load history: {exc}")

        elif choice == "4":
            print("\nExiting agent.")
            break

        else:
            print("\n[!] Invalid option.")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
