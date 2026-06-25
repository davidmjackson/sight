"""Goal B reconciler: per-ticket status-vs-activity watermelon logic."""

from sprintsight.connect.github import PR, Activity
from sprintsight.crosstool import reconcile, run_cross_tool


def _v(status, activity, key="SSSB-1", team="Atlas"):
    return reconcile({"ticket": {"key": key, "status": status, "team": team}, "activity": activity})


def test_in_progress_no_work_is_watermelon():
    v = _v("In Progress", None)
    assert v.is_watermelon is True
    assert v.actual_status == "red"
    assert "jira-SSSB-1" in v.evidence
    assert "github:no-ref:SSSB-1" in v.evidence


def test_done_with_open_pr_is_watermelon():
    act = Activity("SSSB-1", False, [PR(12, "open", False, "t", "u")], 0, None)
    v = _v("Done", act)
    assert v.is_watermelon is True
    assert v.actual_status == "red"
    assert "github:PR#12:open-unmerged" in v.evidence


def test_in_progress_with_work_is_clean():
    act = Activity("SSSB-1", True, [PR(5, "open", False, "t", "u")], 3, None)
    v = _v("In Progress", act)
    assert v.is_watermelon is False
    assert v.actual_status == "green"


def test_done_with_merged_pr_is_clean():
    act = Activity("SSSB-1", False, [PR(8, "closed", True, "t", "u")], 0, None)
    v = _v("Done", act)
    assert v.is_watermelon is False
    assert v.actual_status == "green"


def test_backlog_ticket_is_never_a_watermelon():
    v = _v("To Do", None)
    assert v.is_watermelon is False


def test_run_cross_tool_flags_only_watermelons():
    tickets = {
        "SSSB-1": {"key": "SSSB-1", "status": "In Progress", "team": "Atlas"},
        "SSSB-2": {"key": "SSSB-2", "status": "Done", "team": "Atlas"},
    }
    act = {"SSSB-2": Activity("SSSB-2", True, [PR(8, "closed", True, "t", "u")], 1, None)}
    verdicts = run_cross_tool(tickets, act)
    flagged = [v for v in verdicts if v.is_watermelon]
    assert [v.team for v in verdicts] == ["Atlas", "Atlas"]  # one verdict per ticket
    assert len(flagged) == 1  # SSSB-1 (no work); SSSB-2 has a merged PR
    assert "jira-SSSB-1" in flagged[0].evidence
