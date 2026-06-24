"""Pure translation: a stable simplified Jira issue dict -> the corpus `Artifact` shape.

No network here. The simplified dict (produced by `connector.fetch_issues`) hides Jira's raw
custom-field shape, so this stays trivially testable and deterministic.
"""

from typing import Any

from sprintsight.evals.fixtures import Artifact


def render_body(issue: dict[str, Any]) -> str:
    """Markdown render of one issue: the human-readable, citable text that gets embedded."""
    meta_line = (
        f"**Key:** {issue['key']} · **Status:** {issue.get('status', '')} · "
        f"**Sprint:** {issue.get('sprint', '')} · **Points:** {issue.get('story_points', '')} · "
        f"**Assignee:** {issue.get('assignee') or ''}"
    )
    parts = [f"# {issue.get('summary', issue['key'])}", "", meta_line]
    description = (issue.get("description") or "").strip()
    if description:
        parts += ["", description]
    comments = issue.get("comments") or []
    if comments:
        parts += ["", "## Comments"] + [f"- {c}" for c in comments]
    return "\n".join(parts)


def normalize(issue: dict[str, Any]) -> Artifact:
    """Map one simplified Jira issue dict to an Artifact. Pure; same input -> same output."""
    key = issue["key"]
    return Artifact(
        artifact_id=f"jira-{key}",
        source_type="jira",
        team=issue.get("team", ""),
        sprint=int(issue.get("sprint", 0)),
        meta={
            "source_ref": key,
            "title": issue.get("summary"),
            "author": issue.get("assignee") or issue.get("reporter"),
            "source_timestamp": issue.get("updated"),
        },
        body=render_body(issue),
    )
