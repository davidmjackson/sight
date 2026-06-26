import pytest

from sprintsight.web import crosstool_service
from sprintsight.web.crosstool_service import (
    _active_source,
    _crosstool_live_enabled,
    _github_citation,
    _jira_citation,
    crosstool_view,
)

_RANK = {"watermelon": 0, "stalled": 1, "clean": 2}


def test_jira_citation_reads_as_prose():
    assert _jira_citation("SSSB-1", "In Progress") == "Jira SSSB-1 (In Progress)"


def test_github_citation_mapping():
    assert _github_citation("github:no-ref:SSSB-1") == (
        "GitHub: no linked branch, PR, or commit"
    )
    assert _github_citation("github:no-merged-pr:SSSB-9") == (
        "GitHub: work exists but nothing merged"
    )
    assert _github_citation("github:active:SSSB-3") == "GitHub: active, linked work found"
    assert _github_citation("github:n/a:SSSB-4") == "GitHub: ticket not claiming progress"
    assert _github_citation("github:PR#12:open-unmerged") == (
        "GitHub: PR #12 is open and unmerged"
    )
    assert _github_citation("github:PR#20:stalled-17d") == (
        "GitHub: PR #20 has had no activity for 17 days"
    )


def test_summary_counts_match_fixtures():
    page = crosstool_view()
    assert page.summary.checked == 4
    assert page.summary.watermelons == 2
    assert page.summary.stalled == 1
    assert page.summary.as_of == "2026-06-25T00:00:00Z"


def test_rows_are_flagged_first():
    classes = [r.classification for r in crosstool_view().rows]
    assert classes == sorted(classes, key=lambda c: _RANK[c])
    assert classes[0] == "watermelon"
    assert classes[-1] == "clean"


def test_each_flagged_row_cites_both_tools():
    flagged = [r for r in crosstool_view().rows if r.classification != "clean"]
    assert flagged
    for r in flagged:
        assert r.jira_citation.startswith("Jira ")
        assert r.github_citation.startswith("GitHub:")


def test_stalled_row_citation_names_the_stalled_pr():
    stalled = [r for r in crosstool_view().rows if r.classification == "stalled"]
    assert len(stalled) == 1
    assert "no activity" in stalled[0].github_citation


def _fake_live_source():
    # one "In Progress" ticket with no GitHub activity -> a watermelon
    tickets = [{"key": "SSSB-1", "status": "In Progress", "team": "Atlas"}]
    activity = {}
    return tickets, activity, "2026-07-01T12:00:00Z", "live"


def test_live_source_shapes_page_with_live_mode():
    page = crosstool_view(source=_fake_live_source)
    assert page.summary.mode == "live"
    assert page.summary.as_of == "2026-07-01T12:00:00Z"
    assert page.summary.checked == 1
    assert page.summary.watermelons == 1
    row = page.rows[0]
    assert row.key == "SSSB-1"
    assert row.jira_citation.startswith("Jira ")
    assert row.github_citation.startswith("GitHub:")


def test_default_source_is_offline(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_CROSSTOOL_LIVE", raising=False)
    page = crosstool_view()
    assert page.summary.mode == "offline"
    assert page.summary.checked == 4


def test_live_failure_falls_back_to_offline_failed(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_LIVE", "on")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("COMPOSIO_API_KEY", "x")
    monkeypatch.setenv("COMPOSIO_CONNECTED_ACCOUNT_ID", "ca_x")
    monkeypatch.setenv("COMPOSIO_USER_ID", "user_x")
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_REPO", "owner/repo")
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_PROJECT", "SSSB")

    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(crosstool_service, "_live_source", boom)
    page = crosstool_view(source=_active_source)
    assert page.summary.mode == "offline-failed"
    assert page.summary.checked == 4  # fell back to the fixtures


# ---------------------------------------------------------------------------
# Gate fail-safe: any one missing credential must disable live mode
# ---------------------------------------------------------------------------

_ALL_LIVE_ENV = {
    "SPRINTSIGHT_CROSSTOOL_LIVE": "on",
    "GITHUB_TOKEN": "x",
    "COMPOSIO_API_KEY": "x",
    "COMPOSIO_CONNECTED_ACCOUNT_ID": "ca_x",
    "COMPOSIO_USER_ID": "user_x",
    "SPRINTSIGHT_CROSSTOOL_REPO": "owner/repo",
    "SPRINTSIGHT_CROSSTOOL_PROJECT": "SSSB",
}


@pytest.mark.parametrize(
    "omitted",
    [
        "SPRINTSIGHT_CROSSTOOL_LIVE",
        "GITHUB_TOKEN",
        "COMPOSIO_API_KEY",
        "COMPOSIO_CONNECTED_ACCOUNT_ID",
        "COMPOSIO_USER_ID",
        "SPRINTSIGHT_CROSSTOOL_REPO",
        "SPRINTSIGHT_CROSSTOOL_PROJECT",
        None,  # all seven present -> gate must be True
    ],
)
def test_live_gate_requires_all_seven_credentials(monkeypatch, omitted):
    """Gate is False when any single credential is absent; True only with all seven."""
    for key, value in _ALL_LIVE_ENV.items():
        if key != omitted:
            monkeypatch.setenv(key, value)
        else:
            monkeypatch.delenv(key, raising=False)
    if omitted is None:
        assert _crosstool_live_enabled() is True
    else:
        assert _crosstool_live_enabled() is False
