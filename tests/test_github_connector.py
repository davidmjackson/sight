"""Stage 7 cross-tool connector (Goal B): GitHub activity indexing, offline."""


from sprintsight.connect.github import (
    GitHubConnector,
    RecordedGitHubConnector,
    index_activity,
)

ITEMS = [
    {"type": "branch", "name": "feature/SSSB-4-auth-refresh"},
    {"type": "pr", "number": 12, "title": "SSSB-4 auth refresh", "state": "open",
     "merged": False, "url": "https://gh/pr/12"},
    {"type": "commit", "message": "SSSB-4 wip on refresh", "committed_at": "2026-06-20T10:00:00Z"},
    {"type": "commit", "message": "SSSB-4 more", "committed_at": "2026-06-21T10:00:00Z"},
    {"type": "pr", "number": 30, "title": "SSSB-9 ship dashboard", "state": "closed",
     "merged": True, "url": "https://gh/pr/30"},
]


def test_index_groups_facts_by_key():
    idx = index_activity(ITEMS)
    assert set(idx) == {"SSSB-4", "SSSB-9"}

    a4 = idx["SSSB-4"]
    assert a4.has_branch is True
    assert a4.commit_count == 2
    assert a4.last_commit_at == "2026-06-21T10:00:00Z"  # newest wins
    assert [p.number for p in a4.prs] == [12]
    assert a4.prs[0].merged is False and a4.prs[0].state == "open"

    a9 = idx["SSSB-9"]
    assert a9.has_branch is False
    assert a9.commit_count == 0
    assert a9.prs[0].merged is True


def test_index_ignores_text_without_a_key():
    assert index_activity([{"type": "commit", "message": "no ticket here"}]) == {}


def test_index_does_not_false_join_on_embedded_run():
    # A key glued inside a larger token must not match (word-bounded KEY_RE).
    assert index_activity([{"type": "commit", "message": "xSSSB-4y not a real ref"}]) == {}


def test_recorded_connector_indexes_from_file(tmp_path):
    sample = tmp_path / "gh.json"
    sample.write_text(
        '[{"type": "pr", "number": 7, "title": "SSSB-2 wire login", '
        '"state": "closed", "merged": true, "url": "u"}]',
        encoding="utf-8",
    )
    idx = RecordedGitHubConnector.from_file(sample).fetch_activity()
    assert set(idx) == {"SSSB-2"}
    assert idx["SSSB-2"].prs[0].merged is True


def test_index_carries_pr_updated_at():
    items = [{"type": "pr", "number": 9, "title": "SSSB-8 wip", "state": "open",
              "merged": False, "url": "u", "updated_at": "2026-06-15T00:00:00Z"}]
    idx = index_activity(items)
    assert idx["SSSB-8"].prs[0].updated_at == "2026-06-15T00:00:00Z"


def test_pr_updated_at_defaults_to_none():
    items = [{"type": "pr", "number": 9, "title": "SSSB-8", "state": "open",
              "merged": False, "url": "u"}]
    idx = index_activity(items)
    assert idx["SSSB-8"].prs[0].updated_at is None


def test_github_connector_uses_injected_fetcher():
    fake_items = [{"type": "branch", "name": "feat/SSSB-5-thing"}]
    conn = GitHubConnector("owner/repo", fetcher=lambda repo: fake_items)
    idx = conn.fetch_activity()
    assert set(idx) == {"SSSB-5"}
    assert idx["SSSB-5"].has_branch is True
