
import os
import requests

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI


REPO = "zdr4k/DE-TH-Sentinel-DaC"
BRANCH = "main"
RULES_PATH = "Rules"


class RuleSelection(BaseModel):
    filename: str = Field(
        description="Exact filename selected from the provided list"
    )
    reason: str = Field(
        description="Brief reason for selecting this detection rule"
    )


def list_detection_rules() -> list[str]:
    url = (
        f"https://api.github.com/repos/{REPO}"
        f"/git/trees/{BRANCH}?recursive=1"
    )

    headers = {
        "Accept": "application/vnd.github+json"
    }

    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    if data.get("truncated"):
        raise RuntimeError(
            "GitHub returned an incomplete repository tree."
        )

    rules = [
        item["path"].removeprefix(f"{RULES_PATH}/")
        for item in data.get("tree", [])
        if item["type"] == "blob"
        and item["path"].startswith(f"{RULES_PATH}/")
        and item["path"].lower().endswith((".yml", ".yaml"))
    ]

    return sorted(rules)


def select_detection_rule() -> dict:
    rules = list_detection_rules()

    if not rules:
        raise RuntimeError("No detection rules found.")

    print(f"\n[GitHub] Found {len(rules)} detection rules.")

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    ).with_structured_output(RuleSelection)

    result = llm.invoke(
        "You are a detection engineering assistant.\n"
        "Select ONE detection rule suitable for a simple, "
        "read-only validation demonstration.\n"
        "Prefer rules with clear MITRE ATT&CK mappings "
        "and straightforward telemetry requirements.\n"
        "You only have filenames, not rule contents. "
        "Do not claim to have inspected the queries.\n"
        "Return the exact filename from the list.\n\n"
        f"Available rules:\n" + "\n".join(rules)
    )

    if result.filename not in rules:
        raise ValueError(
            "The LLM selected a rule outside the repository list."
        )

    return {
        "filename": result.filename,
        "reason": result.reason,
    }
