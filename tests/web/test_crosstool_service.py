from sprintsight.web.crosstool_service import (
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
