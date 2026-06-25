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


def test_done_with_work_but_no_pr_is_watermelon_with_clear_token():
    act = Activity("SSSB-1", True, [], 4, None)  # branch + commits, never a PR
    v = _v("Done", act)
    assert v.is_watermelon is True
    assert v.actual_status == "red"
    assert "github:no-merged-pr:SSSB-1" in v.evidence


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


AS_OF = "2026-06-25T00:00:00+00:00"


def _vt(status, activity, as_of=None, key="SSSB-1", team="Atlas"):
    return reconcile({
        "ticket": {"key": key, "status": status, "team": team},
        "activity": activity,
        "as_of": as_of,
    })


def _open_pr_act(number, updated_at, key="SSSB-1"):
    return Activity(key, False, [PR(number, "open", False, "t", "u", updated_at)], 0, None)


def test_in_progress_parked_pr_is_amber_not_watermelon():
    v = _vt("In Progress", _open_pr_act(20, "2026-06-15T00:00:00Z"), AS_OF)
    assert v.actual_status == "amber"
    assert v.is_watermelon is False
    assert "github:PR#20:stalled-10d" in v.evidence
    assert "jira-SSSB-1" in v.evidence


def test_in_progress_fresh_pr_is_green():
    v = _vt("In Progress", _open_pr_act(21, "2026-06-24T00:00:00Z"), AS_OF)
    assert v.actual_status == "green"
    assert v.is_watermelon is False


def test_stalled_boundary_is_inclusive_at_threshold():
    at7 = _vt("In Progress", _open_pr_act(1, "2026-06-18T00:00:00Z"), AS_OF)  # exactly 7 days
    at6 = _vt("In Progress", _open_pr_act(1, "2026-06-19T00:00:00Z"), AS_OF)  # 6 days
    assert at7.actual_status == "amber"
    assert at6.actual_status == "green"


def test_no_as_of_skips_staleness_backcompat():
    v = _vt("In Progress", _open_pr_act(20, "2026-01-01T00:00:00Z"), None)
    assert v.actual_status == "green"


def test_run_cross_tool_threads_as_of_for_stalled():
    tickets = {"SSSB-7": {"key": "SSSB-7", "status": "In Progress", "team": "Atlas"}}
    act = {"SSSB-7": _open_pr_act(20, "2026-06-15T00:00:00Z", key="SSSB-7")}
    verdicts = run_cross_tool(tickets, act, as_of="2026-06-25T00:00:00+00:00")
    assert verdicts[0].actual_status == "amber"
    assert not verdicts[0].is_watermelon


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
