from sprintsight.web.crosstool_service import _github_citation, _jira_citation


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
