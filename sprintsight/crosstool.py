"""Cross-tool watermelon reconciler (Goal B, SS-5).

Pure, recommend-only. Compares one Jira ticket's reported status against its GitHub Activity
and emits the existing SS-1.4 `Verdict`. The red rule (v1): a ticket claiming progress with no
linked work, or a Done ticket whose PR is still open/unmerged, is "actually red" while it reads
as healthy in Jira, i.e. a watermelon. A third colour, amber, flags a parked open PR (no activity
for `stale_after_days`, measured against an injected `as_of`): a warning, not a watermelon.
Never writes to GitHub or Jira.
"""

from datetime import UTC, datetime
from typing import Any

from sprintsight.connect.github import Activity
from sprintsight.evals.watermelon import Verdict

_PROGRESS = {"in progress", "in review", "done"}


def _has_work(activity: Activity | None) -> bool:
    return activity is not None and (
        activity.has_branch or bool(activity.prs) or activity.commit_count > 0
    )


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _stalled(
    activity: Activity | None, as_of: str | None, threshold_days: int
) -> tuple[int, int] | None:
    """If the newest open PR (and any commits) have been quiet >= threshold_days as of
    `as_of`, return (pr_number, age_days); else None. Pure; None as_of skips the check."""
    now = _parse_ts(as_of)
    if activity is None or now is None:
        return None
    open_prs = [p for p in activity.prs if not p.merged]
    if not open_prs:
        return None
    floor = datetime.min.replace(tzinfo=UTC)
    newest_pr = max(open_prs, key=lambda p: _parse_ts(p.updated_at) or floor)
    stamps = [
        t
        for t in (_parse_ts(newest_pr.updated_at), _parse_ts(activity.last_commit_at))
        if t is not None
    ]
    if not stamps:
        return None
    age_days = (now - max(stamps)).days
    if age_days >= threshold_days:
        return newest_pr.number, age_days
    return None


def reconcile(inputs: dict[str, Any]) -> Verdict:
    """`inputs = {"ticket": {key,status,team}, "activity": Activity | None}` -> Verdict."""
    ticket = inputs["ticket"]
    activity: Activity | None = inputs.get("activity")
    key = ticket["key"]
    team = ticket.get("team", "")
    status = str(ticket.get("status", "")).strip().lower()
    as_of = inputs.get("as_of")
    stale_after_days = int(inputs.get("stale_after_days", 7))

    reported = "green" if status in _PROGRESS else "n/a"

    # actual_status and the GitHub-side evidence token.
    open_prs = [p for p in (activity.prs if activity else []) if not p.merged]
    if status == "done":
        merged = any(p.merged for p in activity.prs) if activity else False
        if merged:
            actual, gh = "green", f"github:active:{key}"
        elif open_prs:
            actual, gh = "red", f"github:PR#{open_prs[0].number}:open-unmerged"
        elif _has_work(activity):
            # Branch/commits exist but nothing merged: real work, not shipped.
            actual, gh = "red", f"github:no-merged-pr:{key}"
        else:
            actual, gh = "red", f"github:no-ref:{key}"
    elif status in {"in progress", "in review"}:
        if not _has_work(activity):
            actual, gh = "red", f"github:no-ref:{key}"
        else:
            stalled = _stalled(activity, as_of, stale_after_days)
            if stalled is not None:
                pr_number, age_days = stalled
                actual, gh = "amber", f"github:PR#{pr_number}:stalled-{age_days}d"
            else:
                actual, gh = "green", f"github:active:{key}"
    else:  # To Do / Backlog: not claiming progress, never a watermelon.
        actual, gh = "green", f"github:n/a:{key}"

    is_watermelon = reported == "green" and actual == "red"
    cite_github = is_watermelon or actual == "amber"
    evidence = [f"jira-{key}", gh] if cite_github else [f"jira-{key}"]

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
    as_of: str | None = None,
    stale_after_days: int = 7,
) -> list[Verdict]:
    """Reconcile every Jira ticket against its GitHub activity (matched by key)."""
    return [
        reconcile({
            "ticket": ticket,
            "activity": activity.get(key),
            "as_of": as_of,
            "stale_after_days": stale_after_days,
        })
        for key, ticket in tickets.items()
    ]
