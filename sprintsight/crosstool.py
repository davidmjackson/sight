"""Cross-tool watermelon reconciler (Goal B, SS-5).

Pure, recommend-only. Compares one Jira ticket's reported status against its GitHub Activity
and emits the existing SS-1.4 `Verdict`. The red rule (v1): a ticket claiming progress with no
linked work, or a Done ticket whose PR is still open/unmerged, is "actually red" while it reads
as healthy in Jira, i.e. a watermelon. Colours are green/red only; amber is reserved for the
deferred staleness signal. Never writes to GitHub or Jira.
"""

from typing import Any

from sprintsight.connect.github import Activity
from sprintsight.evals.watermelon import Verdict

_PROGRESS = {"in progress", "in review", "done"}


def _has_work(activity: Activity | None) -> bool:
    return activity is not None and (
        activity.has_branch or bool(activity.prs) or activity.commit_count > 0
    )


def reconcile(inputs: dict[str, Any]) -> Verdict:
    """`inputs = {"ticket": {key,status,team}, "activity": Activity | None}` -> Verdict."""
    ticket = inputs["ticket"]
    activity: Activity | None = inputs.get("activity")
    key = ticket["key"]
    team = ticket.get("team", "")
    status = str(ticket.get("status", "")).strip().lower()

    reported = "green" if status in _PROGRESS else "n/a"

    # actual_status and the GitHub-side evidence token.
    open_prs = [p for p in (activity.prs if activity else []) if not p.merged]
    if status == "done":
        merged = any(p.merged for p in activity.prs) if activity else False
        if merged:
            actual, gh = "green", f"github:active:{key}"
        elif open_prs:
            actual, gh = "red", f"github:PR#{open_prs[0].number}:open-unmerged"
        else:
            actual, gh = "red", f"github:no-ref:{key}"
    elif status in {"in progress", "in review"}:
        if _has_work(activity):
            actual, gh = "green", f"github:active:{key}"
        else:
            actual, gh = "red", f"github:no-ref:{key}"
    else:  # To Do / Backlog: not claiming progress, never a watermelon.
        actual, gh = "green", f"github:n/a:{key}"

    is_watermelon = reported == "green" and actual == "red"
    evidence = [f"jira-{key}", gh] if is_watermelon else [f"jira-{key}"]

    verb = (
        "looks healthier than its code activity"
        if is_watermelon
        else "matches its code activity"
    )
    explanation = f"{key} reported {reported}; computed actual {actual} ({verb})."

    return Verdict(
        team=team,
        reported_status=reported,
        actual_status=actual,
        is_watermelon=is_watermelon,
        evidence=evidence,
        signals=[gh],
        explanation=explanation,
    )


def run_cross_tool(
    tickets: dict[str, dict[str, Any]],
    activity: dict[str, Activity],
) -> list[Verdict]:
    """Reconcile every Jira ticket against its GitHub activity (matched by key)."""
    return [
        reconcile({"ticket": ticket, "activity": activity.get(key)})
        for key, ticket in tickets.items()
    ]
