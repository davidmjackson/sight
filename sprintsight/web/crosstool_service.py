"""Stage 7 web data layer for the cross-tool watermelon (SS-5).

Reads two captured fixtures (Jira tickets + GitHub items), runs the existing pure
`reconcile()` per ticket against a pinned `as_of`, and shapes the verdicts into view-models
for the `/crosstool` page: a summary band and a flagged-first list with plain-English
citations of BOTH tools. Offline is the default: no network in a request and no clock, so
the page is deterministic. The live gate (`SPRINTSIGHT_CROSSTOOL_LIVE=on` + credentials)
switches to real connectors; any live failure falls back honestly to `mode="offline-failed"`.
The burndown world (`service.py`) and every eval gate are untouched.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sprintsight.connect.connector import JiraConnector
from sprintsight.connect.github import Activity, GitHubConnector, RecordedGitHubConnector
from sprintsight.connect.jira_tickets import tickets_from_artifacts
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


@dataclass(frozen=True)
class CrossToolSummary:
    checked: int
    watermelons: int
    stalled: int
    as_of: str
    mode: str


@dataclass(frozen=True)
class CrossToolRow:
    key: str
    team: str
    reported_status: str
    actual_status: str
    classification: str  # "watermelon" | "stalled" | "clean"
    headline: str
    jira_citation: str
    github_citation: str


@dataclass(frozen=True)
class CrossToolPage:
    summary: CrossToolSummary
    rows: list[CrossToolRow]


_SORT_RANK = {"watermelon": 0, "stalled": 1, "clean": 2}


def _classification(verdict: Verdict) -> str:
    if verdict.is_watermelon:
        return "watermelon"
    if verdict.actual_status == "amber":
        return "stalled"
    return "clean"


# ---------------------------------------------------------------------------
# Source seam: gate helpers + three source functions
# (defined BEFORE crosstool_view so the default-arg reference resolves)
# ---------------------------------------------------------------------------

_LIVE_FLAG = "SPRINTSIGHT_CROSSTOOL_LIVE"


def _crosstool_config() -> tuple[str, str] | None:
    """The configured (repo, project) for a live read, or None when either is missing."""
    repo = os.environ.get("SPRINTSIGHT_CROSSTOOL_REPO", "")
    project = os.environ.get("SPRINTSIGHT_CROSSTOOL_PROJECT", "")
    return (repo, project) if repo and project else None


def _crosstool_live_enabled() -> bool:
    """True only when the live switch is deliberately on AND every credential and the
    repo/project are present (fail-safe). Any missing piece falls back to offline."""
    return (
        os.environ.get(_LIVE_FLAG) == "on"
        and bool(os.environ.get("GITHUB_TOKEN"))
        and bool(os.environ.get("COMPOSIO_API_KEY"))
        and _crosstool_config() is not None
    )


def _offline_source() -> tuple[list[dict], dict[str, Activity], str, str]:
    """The frozen replay: two fixtures, a pinned clock. No network. Unchanged behaviour."""
    tickets = json.loads(_JIRA_FIXTURE.read_text(encoding="utf-8"))
    activity = RecordedGitHubConnector.from_file(_GITHUB_FIXTURE).fetch_activity()
    return tickets, activity, CROSSTOOL_AS_OF, "offline"


def _live_source() -> tuple[list[dict], dict[str, Activity], str, str]:
    """The live read: real Jira tickets + real GitHub activity, real clock. Gate guarantees
    the config is present before this is called."""
    repo, project = _crosstool_config()  # type: ignore[misc]
    tickets = list(tickets_from_artifacts(JiraConnector(project).fetch()).values())
    activity = GitHubConnector(repo).fetch_activity()
    return tickets, activity, datetime.now(UTC).isoformat(), "live"


def _active_source() -> tuple[list[dict], dict[str, Activity], str, str]:
    """Live when the gate is open, else offline. A live failure is honest: it falls back to the
    offline replay and reports `offline-failed` rather than 500-ing or faking live data."""
    if not _crosstool_live_enabled():
        return _offline_source()
    try:
        return _live_source()
    except Exception:
        tickets, activity, _as_of, _mode = _offline_source()
        return tickets, activity, CROSSTOOL_AS_OF, "offline-failed"


# ---------------------------------------------------------------------------
# View builder
# ---------------------------------------------------------------------------


def crosstool_view(
    source: Callable[[], tuple[list[dict], dict[str, Activity], str, str]] = _active_source,
) -> CrossToolPage:
    """Reconcile every ticket against its GitHub activity and shape the page.

    The `source` supplies (tickets, activity, as_of, mode); default `_active_source` is offline
    unless the live gate is open. Pure given its source: the web layer pairs each ticket key with
    its verdict here (a `Verdict` carries no key), so every row keeps its citation.
    """
    tickets, activity, as_of, mode = source()
    rows: list[CrossToolRow] = []
    for t in tickets:
        key, status, team = t["key"], t.get("status", ""), t.get("team", "")
        verdict = reconcile(
            {"ticket": t, "activity": activity.get(key), "as_of": as_of}
        )
        signal = verdict.signals[0] if verdict.signals else ""
        rows.append(
            CrossToolRow(
                key=key,
                team=team,
                reported_status=verdict.reported_status,
                actual_status=verdict.actual_status,
                classification=_classification(verdict),
                headline=verdict.explanation,
                jira_citation=_jira_citation(key, status),
                github_citation=_github_citation(signal),
            )
        )
    rows.sort(key=lambda r: (_SORT_RANK[r.classification], r.key))
    summary = CrossToolSummary(
        checked=len(rows),
        watermelons=sum(1 for r in rows if r.classification == "watermelon"),
        stalled=sum(1 for r in rows if r.classification == "stalled"),
        as_of=as_of,
        mode=mode,
    )
    return CrossToolPage(summary=summary, rows=rows)
