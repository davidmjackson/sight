"""The connector seam: a `Connector` returns corpus Artifacts. `RecordedConnector` reads a saved
sample (offline twin); `JiraConnector` pulls from the live board via the Composio SDK. Same seam
pattern as the embedder / store / auth / writer seams.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from sprintsight.connect.normalize import normalize
from sprintsight.evals.fixtures import Artifact


class Connector(Protocol):
    def fetch(self) -> dict[str, Artifact]: ...


def _to_artifacts(issues: list[dict[str, Any]]) -> dict[str, Artifact]:
    artifacts = [normalize(i) for i in issues]
    return {a.artifact_id: a for a in artifacts}


class RecordedConnector:
    """Offline twin: normalizes a recorded list of simplified issue dicts. No network."""

    def __init__(self, issues: list[dict[str, Any]]) -> None:
        self._issues = issues

    @classmethod
    def from_file(cls, path: str | Path) -> "RecordedConnector":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def fetch(self) -> dict[str, Artifact]:
        return _to_artifacts(self._issues)


def _issues_from_response(resp: Any) -> list[dict[str, Any]]:
    """Pull the issue list out of a Composio ToolExecutionResponse, raising on a failed
    call so the caller's fail-safe gate can fall back to offline. `data` is already the
    tool's data dict in the new SDK (no outer envelope)."""
    if not getattr(resp, "successful", True):
        raise RuntimeError(
            f"Composio JIRA_SEARCH_ISSUES failed: {getattr(resp, 'error', None)}"
        )
    data = getattr(resp, "data", resp) or {}
    return data.get("issues", []) or []


def fetch_issues(project_key: str) -> list[dict[str, Any]]:
    """Network: pull issues for `project_key` from Jira via the Composio client, reusing the
    already-connected Jira account identified by `COMPOSIO_CONNECTED_ACCOUNT_ID`, and return
    stable simplified issue dicts.

    The `Composio` client (composio>=0.16) is imported lazily so the module imports without it
    installed and so no test touches the network (tests inject a fake fetcher into JiraConnector
    instead, or monkeypatch a fake `composio` module for the wiring test).

    The exact Composio action slug and Jira custom-field IDs (sprint, story points) are confirmed
    at live-run time against the connected account; `_to_clean` is the single place that mapping
    lives. Until a live run, use RecordedConnector.
    """
    from composio import Composio  # lazy: runtime-only dependency

    composio = Composio()  # reads COMPOSIO_API_KEY from the environment
    resp = composio.tools.execute(
        "JIRA_SEARCH_ISSUES",
        arguments={
            "jql": f"project = {project_key} ORDER BY updated DESC",
            "fields": ["summary", "status", "labels", "description", "updated", "assignee"],
            "max_results": 100,
        },
        connected_account_id=os.environ["COMPOSIO_CONNECTED_ACCOUNT_ID"],
    )
    return [_to_clean(issue) for issue in _issues_from_response(resp)]


def _team_from_labels(labels: list[str]) -> str:
    for label in labels or []:
        if label.startswith("team:"):
            return label.split(":", 1)[1].capitalize()
    return ""


def _name_of(value: Any) -> Any:
    """Composio may return assignee/reporter as a dict (display_name) or a bare string/None."""
    if isinstance(value, dict):
        return value.get("display_name") or value.get("displayName")
    return value


def _to_clean(raw: dict[str, Any]) -> dict[str, Any]:
    """Map one Composio Jira issue to the stable simplified dict normalize() expects.

    Calibrated against the real Composio JIRA_SEARCH_ISSUES response (verified live on project
    SSSB, 2026-06-24): issues are FLAT (no raw-Jira `fields` nesting), `description` arrives as a
    plain string (Composio flattens ADF for us), `status` is a dict with `name`, and `reporter`/
    `assignee` are dicts with `display_name`. A team-managed kanban board has no sprint, so sprint
    defaults to 0; the team rides in a `team:<name>` label. This is the single home for that
    mapping — if a future board returns ADF or a sprint field, adjust only here.
    """
    status = raw.get("status")
    return {
        "key": raw.get("key", ""),
        "summary": raw.get("summary", ""),
        "status": status.get("name", "") if isinstance(status, dict) else (status or ""),
        "team": _team_from_labels(raw.get("labels") or []),
        "sprint": int(raw.get("sprint") or 0),
        "story_points": raw.get("story_points"),
        "assignee": _name_of(raw.get("assignee")),
        "reporter": _name_of(raw.get("reporter")),
        "updated": raw.get("updated"),
        "description": raw.get("description") if isinstance(raw.get("description"), str) else "",
        "comments": [
            c.get("body", "") if isinstance(c, dict) else str(c)
            for c in (raw.get("comments") or [])
        ],
    }


class JiraConnector:
    """Live connector. `fetcher` is injectable so tests run without a network."""

    def __init__(
        self,
        project_key: str,
        fetcher: Callable[[str], list[dict[str, Any]]] = fetch_issues,
    ) -> None:
        self._project_key = project_key
        self._fetcher = fetcher

    def fetch(self) -> dict[str, Artifact]:
        return _to_artifacts(self._fetcher(self._project_key))
