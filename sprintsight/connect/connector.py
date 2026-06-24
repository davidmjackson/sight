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
        params={"jql": f"project = {project_key} ORDER BY updated DESC", "maxResults": 100},
    )
    return [_to_clean(issue) for issue in raw.get("data", {}).get("issues", [])]


def _to_clean(raw: dict[str, Any]) -> dict[str, Any]:
    """Map one raw Jira API issue to the stable simplified dict normalize() expects.

    Single home for Jira's custom-field mess. Field IDs below are the Jira Cloud defaults for a
    team-managed project; confirm against the connected account on the first live run.
    """
    f = raw.get("fields", {})
    team = ""
    for label in f.get("labels", []) or []:
        if label.startswith("team:"):
            team = label.split(":", 1)[1].capitalize()
            break
    sprint = 0
    sprint_field = f.get("customfield_10020") or []
    if sprint_field:
        name = (sprint_field[-1] or {}).get("name", "")
        digits = "".join(ch for ch in name if ch.isdigit())
        sprint = int(digits) if digits else 0
    comments = [c.get("body", "") for c in (f.get("comment", {}) or {}).get("comments", [])]
    return {
        "key": raw.get("key", ""),
        "summary": f.get("summary", ""),
        "status": (f.get("status", {}) or {}).get("name", ""),
        "team": team,
        "sprint": sprint,
        "story_points": f.get("customfield_10016"),
        "assignee": (f.get("assignee") or {}).get("displayName"),
        "reporter": (f.get("reporter") or {}).get("displayName"),
        "updated": f.get("updated"),
        "description": f.get("description") or "",
        "comments": comments,
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
