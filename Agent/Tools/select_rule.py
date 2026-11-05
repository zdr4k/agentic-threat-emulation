"""
select_rule: list the detection rules in the DaC repo and let the model pick
one to validate. Returns {"filename": ..., "reason": ...}.

Env:
  DAC_REPO        owner/name of the DaC repo (default zdr4k/de-th-sentinel-dac)
  DAC_RULES_PATH  folder holding the rules (default Rules)
  ISSUE_TOKEN / GITHUB_TOKEN  optional, raises the GitHub API rate limit
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

REPO = os.getenv("DAC_REPO", "zdr4k/de-th-sentinel-dac")
RULES_PATH = os.getenv("DAC_RULES_PATH", "Rules")


def list_rule_files() -> list[str]:
    """Rule YAML file names in the repo's Rules folder, via the GitHub API."""
    url = f"https://api.github.com/repos/{REPO}/contents/{RULES_PATH}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.getenv("ISSUE_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        items = json.loads(resp.read().decode("utf-8"))
    return [it["name"] for it in items
            if it.get("type") == "file" and it["name"].endswith((".yml", ".yaml"))]


def select_detection_rule() -> dict:
    """List the rules and let the model pick one, with a one-line reason."""
    files = list_rule_files()
    if not files:
        raise RuntimeError(f"no rule files found in {REPO}/{RULES_PATH}")

    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    msg = model.invoke([
        SystemMessage(content=(
            "You choose one detection rule to validate against live telemetry. "
            'Reply as JSON only: {"filename": "<one of the files>", '
            '"reason": "<one sentence>"}.'
        )),
        HumanMessage(content="Rules:\n" + "\n".join(files)),
    ])
    text = re.sub(r"^```(?:json)?|```$", "", msg.content.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
        filename = data.get("filename", "")
        reason = data.get("reason", "")
    except json.JSONDecodeError:
        filename, reason = "", "model did not return valid JSON"
    if filename not in files:
        filename, reason = files[0], reason or "defaulted to the first rule"
    return {"filename": filename, "reason": reason}
