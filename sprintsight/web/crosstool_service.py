"""Stage 7 web data layer for the cross-tool watermelon (SS-5).

Reads two captured fixtures (Jira tickets + GitHub items), runs the existing pure
`reconcile()` per ticket against a pinned `as_of`, and shapes the verdicts into view-models
for the `/crosstool` page: a summary band and a flagged-first list with plain-English
citations of BOTH tools. Offline only: no network in a request and no clock, so the page is
deterministic. The burndown world (`service.py`) and every eval gate are untouched.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from sprintsight.connect.github import RecordedGitHubConnector
from sprintsight.crosstool import reconcile
from sprintsight.evals.watermelon import Verdict

CROSSTOOL_AS_OF = "2026-06-25T00:00:00Z"

_DATA = Path(__file__).resolve().parents[2] / "data" / "captured"
_JIRA_FIXTURE = _DATA / "crosstool_web_jira.json"
_GITHUB_FIXTURE = _DATA / "crosstool_web_github.json"


def _jira_citation(key: str, status: str) -> str:
    return f"Jira {key} ({status})"


def _github_citation(token: str) -> str:
    """Turn a `Verdict.signals[0]` token into one readable sentence. Pure."""
    parts = token.split(":")
    kind = parts[1] if len(parts) > 1 else ""
    detail = parts[2] if len(parts) > 2 else ""
    if kind == "no-ref":
        return "GitHub: no linked branch, PR, or commit"
    if kind == "no-merged-pr":
        return "GitHub: work exists but nothing merged"
    if kind == "active":
        return "GitHub: active, linked work found"
    if kind == "n/a":
        return "GitHub: ticket not claiming progress"
    if kind.startswith("PR#"):
        number = kind[3:]
        if detail.startswith("stalled-"):
            days = detail[len("stalled-"):].rstrip("d")
            return f"GitHub: PR #{number} has had no activity for {days} days"
        if detail == "open-unmerged":
            return f"GitHub: PR #{number} is open and unmerged"
    return f"GitHub: {token}"
