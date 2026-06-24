"""The connector seam: a `Connector` returns corpus Artifacts. `RecordedConnector` reads a saved
sample (offline twin); `JiraConnector` pulls from the live board via the Composio SDK. Same seam
pattern as the embedder / store / auth / writer seams.
"""

import json
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


def fetch_issues(project_key: str) -> list[dict[str, Any]]:
    """Network: pull issues for `project_key` from Jira via the Composio SDK, reusing the
    already-connected Jira account, and return stable simplified issue dicts.

    The Composio SDK is imported lazily so the module imports without it installed and so no
    test touches the network (tests inject a fake fetcher into JiraConnector instead).

    The exact Composio action slug and Jira custom-field IDs (sprint, story points) are confirmed
    at live-run time against the connected account; `_to_clean` is the single place that mapping
    lives. Until a live run, use RecordedConnector.
    """
    from composio import ComposioToolSet  # lazy: runtime-only dependency

    toolset = ComposioToolSet()
    raw = toolset.execute_action(
        action="JIRA_SEARCH_ISSUES",
        params={
            "jql": f"project = {project_key} ORDER BY updated DESC",
            "fields": ["summary", "status", "labels", "description", "updated", "assignee"],
            "max_results": 100,
        },
    )
    issues = (raw.get("data", {}) or {}).get("issues", [])
    return [_to_clean(issue) for issue in issues]


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
