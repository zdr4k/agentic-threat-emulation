"""
read_rule: loads a detection rule and extracts its id, techniques, table and query.
Parsing only.
"""

from __future__ import annotations

import os
import re
import urllib.request

import yaml
from langchain_core.tools import tool

RAW_BASE = os.environ.get(
    "DAC_RULES_RAW_BASE",
    "https://raw.githubusercontent.com/zdr4k/DE-TH-Sentinel-DaC/main/Rules",
)

_TABLE_RE = re.compile(r"(?m)^\s*([A-Za-z][A-Za-z0-9_]*)\b")
_NOT_TABLES = {"let", "where", "extend", "project", "summarize", "join",
               "union", "print", "range", "search", "datatable"}


def _extract_techniques(mitre_mapping: list) -> list[str]:
    out: list[str] = []
    for block in mitre_mapping or []:
        for t in block.get("techniques", []):
            if t not in out:
                out.append(t)
    return out


def _guess_table(query: str) -> str | None:
    # First bare identifier that is not a let binding or a known operator.
    lines = [ln for ln in query.splitlines()
             if not ln.strip().lower().startswith("let ")]
    for ln in lines:
        m = _TABLE_RE.match(ln)
        if m and m.group(1).lower() not in _NOT_TABLES:
            return m.group(1)
    return None


def _parse(text: str) -> dict:
    data = yaml.safe_load(text)
    query = data.get("query", "")
    techniques = _extract_techniques(data.get("mitre_mapping", []))
    return {
        "id": data["id"],
        "display_name": data.get("display_name", ""),
        "techniques": techniques,
        "primary_technique": techniques[0] if techniques else None,
        "table": _guess_table(query),
        "query": query,
    }


@tool
def read_rule(file_name: str) -> dict:
    """Read a detection rule from the Detection-as-Code repo by its file name.

    Returns a dict with the rule id, the ATT&CK techniques it claims to cover
    (techniques, primary_technique), the source table its query reads, and the
    query itself. Call this first: primary_technique is the technique to emulate,
    and table is the telemetry the check depends on.

    file_name is the rule's YAML file name, e.g. "powershell_encoded_command.yml".
    """
    url = f"{RAW_BASE}/{file_name}"
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        return _parse(resp.read().decode("utf-8"))


def parse_rule_text(text: str) -> dict:
    """Parse rule YAML without the network or the tool wrapper (for tests)."""
    return _parse(text)
