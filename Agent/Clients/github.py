"""
github.py: turn a verdict into a tracking issue in the detection-as-code repo.

A gap or a blind spot becomes an issue the detection engineer can act on, so
the loop ends in the backlog instead of in a console. detected files nothing.
Opening is idempotent by title: a re-run that reaches the same verdict reuses
the open issue instead of filing a duplicate.

Env:
  ISSUE_REPO     owner/name of the DaC repo, e.g. zdr4k/de-th-sentinel-dac
  ISSUE_TOKEN    a token with issues:write on the repo (falls back to
                 GITHUB_TOKEN). Prefer ISSUE_TOKEN: Codespaces injects its own
                 limited GITHUB_TOKEN into the environment, which load_dotenv
                 will not override, so a PAT in .env under GITHUB_TOKEN is
                 silently ignored.
"""

import os

import requests

API = "https://api.github.com"


def _normalize_repo(repo: str) -> str:
    """Accept owner/name, or a full URL, and return owner/name."""
    repo = repo.strip().removesuffix(".git")
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        repo = repo.removeprefix(prefix)
    return repo.strip("/")


class GitHubClient:
    def __init__(self, repo: str | None = None, token: str | None = None):
        repo = repo or os.getenv("ISSUE_REPO")
        self.token = token or os.getenv("ISSUE_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not repo or not self.token:
            raise RuntimeError("set ISSUE_REPO and ISSUE_TOKEN to open issues")
        self.repo = _normalize_repo(repo)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def _existing_open_issue(self, title: str) -> str | None:
        r = requests.get(
            f"{API}/repos/{self.repo}/issues",
            headers=self.headers, params={"state": "open", "per_page": 100},
            timeout=30,
        )
        r.raise_for_status()
        for issue in r.json():
            if issue.get("title") == title and "pull_request" not in issue:
                return issue["html_url"]
        return None

    def open_issue(self, title: str, body: str, labels: list[str] | None = None) -> str:
        existing = self._existing_open_issue(title)
        if existing:
            return existing
        r = requests.post(
            f"{API}/repos/{self.repo}/issues",
            headers=self.headers,
            json={"title": title, "body": body, "labels": labels or []},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["html_url"]


def issue_for(rule: dict, guid: str, window: tuple, verdict: dict):
    """Build (title, body, labels) for a verdict, or None when detected.

    Pure: no network, no env. This is the part worth testing on its own.
    """
    v = verdict["verdict"]
    if v == "detected":
        return None

    if v == "gap":
        title = f"Coverage gap: {rule['display_name']} misses {rule['primary_technique']}"
        labels = ["detection-gap"]
        nxt = "Broaden the rule to cover the variation the atomic exercised."
    elif v == "blind":
        title = f"Collection gap: {rule['table']} blind for {rule['display_name']}"
        labels = ["collection-gap"]
        nxt = "Data never arrived. Check the DCR and the source, not the rule."
    else:
        raise ValueError(f"unknown verdict: {v}")

    body = (
        "Opened by the threat emulation agent.\n\n"
        f"- Rule: `{rule['display_name']}`\n"
        f"- Technique: {rule['primary_technique']}\n"
        f"- Atomic: `{guid}`\n"
        f"- Window: {window[0]} .. {window[1]}\n"
        f"- telemetry_rows: {verdict['telemetry_rows']}, rule_hits: {verdict['rule_hits']}\n\n"
        f"Verdict: **{v}**. {verdict['reason']}\n\n"
        f"Next: {nxt}\n\n"
        f"Rule query:\n```\n{rule['query']}\n```\n"
    )
    return title, body, labels


def report_verdict(rule: dict, guid: str, window: tuple, verdict: dict) -> str | None:
    """File an issue for a gap or blind spot. No-op when detected, or when
    ISSUE_REPO is not set (so test runs do not open issues). Returns the URL."""
    built = issue_for(rule, guid, window, verdict)
    if built is None or not os.getenv("ISSUE_REPO"):
        return None
    title, body, labels = built
    url = GitHubClient().open_issue(title, body, labels)
    print(f"    {verdict['verdict']}: issue -> {url}")
    return url
