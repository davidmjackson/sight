"""Stage 7 connector (Goal A): clean-dict -> Artifact translation, offline."""

from pathlib import Path

from sprintsight.connect.connector import (
    JiraConnector,
    RecordedConnector,
    _issues_from_response,
    _to_clean,
)
from sprintsight.connect.normalize import normalize, render_body
from sprintsight.ingest import ingest_corpus
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.ingest.store import InMemoryStore
from sprintsight.retrieval.retriever import InMemoryRetriever

FIXTURE = Path(__file__).parent / "fixtures" / "jira_sample.json"

SAMPLE_ISSUE = {
    "key": "SSD-12",
    "summary": "Wire auth token refresh",
    "status": "In Progress",
    "team": "Atlas",
    "sprint": 15,
    "story_points": 5,
    "assignee": "Dev One",
    "reporter": "PM Atlas",
    "updated": "2026-05-20T10:00:00Z",
    "description": "Refresh tokens before expiry.",
    "comments": ["heads up, Draco's auth API still isn't ready, this will bite us"],
}


def test_normalize_maps_core_fields():
    art = normalize(SAMPLE_ISSUE)
    assert art.artifact_id == "jira-SSD-12"
    assert art.source_type == "jira"
    assert art.team == "Atlas"
    assert art.sprint == 15
    assert art.meta["source_ref"] == "SSD-12"
    assert art.meta["title"] == "Wire auth token refresh"
    assert art.meta["author"] == "Dev One"  # assignee preferred over reporter
    assert art.meta["source_timestamp"] == "2026-05-20T10:00:00Z"


def test_render_body_carries_key_facts():
    body = render_body(SAMPLE_ISSUE)
    assert "SSD-12" in body
    assert "In Progress" in body
    assert "5" in body  # story points
    assert "Refresh tokens before expiry." in body
    assert "Draco's auth API still isn't ready" in body  # comment text is citable


def test_recorded_connector_returns_artifacts_keyed_by_id():
    conn = RecordedConnector.from_file(FIXTURE)
    artifacts = conn.fetch()
    assert set(artifacts) == {"jira-SSD-12", "jira-SSD-13", "jira-SSD-40"}
    assert all(a.source_type == "jira" for a in artifacts.values())
    assert artifacts["jira-SSD-12"].team == "Atlas"


def test_connector_output_ingests_and_is_retrievable():
    artifacts = RecordedConnector.from_file(FIXTURE).fetch()

    store = InMemoryStore()
    emb = HashingEmbedder()
    report = ingest_corpus(store, emb, artifacts=artifacts)
    assert report.artifacts_total == 3
    assert report.ingested == 3
    assert report.chunks_written >= 3

    # Idempotent: a second run over the same store adds nothing.
    again = ingest_corpus(store, emb, artifacts=artifacts)
    assert again.ingested == 0
    assert again.skipped == 3

    # Retrievable with jira provenance.
    retriever = InMemoryRetriever(emb, artifacts=artifacts)
    results = retriever.search("auth api dependency not ready", team="Atlas")
    assert results, "expected at least one retrieved chunk"
    assert all(r.source_type == "jira" for r in results)
    assert all(r.source_ref.startswith("SSD-") for r in results)


# A real Composio JIRA_SEARCH_ISSUES issue, verified live against project SSSB (2026-06-24):
# flat shape, description as a plain string, status/reporter as dicts, no sprint (kanban board).
REAL_COMPOSIO_ISSUE = {
    "key": "SSSB-1",
    "summary": "Wire auth token refresh",
    "status": {"category": "To Do", "id": "10069", "name": "To Do"},
    "labels": ["sprintsight-demo-data", "team:atlas"],
    "description": "Refresh tokens before expiry; blocked on upstream auth API.",
    "updated": "2026-06-24T17:48:40.615+0100",
    "assignee": None,
    "reporter": {"account_id": "557058:redacted", "display_name": "David Jackson"},
}


def test_to_clean_maps_real_composio_shape():
    clean = _to_clean(REAL_COMPOSIO_ISSUE)
    assert clean["key"] == "SSSB-1"
    assert clean["status"] == "To Do"  # pulled from the status dict's name
    assert clean["team"] == "Atlas"  # from the team: label
    assert clean["sprint"] == 0  # kanban board has no sprint
    assert clean["reporter"] == "David Jackson"  # from the reporter dict's display_name
    assert clean["assignee"] is None
    assert clean["description"].startswith("Refresh tokens")  # plain string, not ADF
    assert clean["comments"] == []
    # And the cleaned dict round-trips through the pure normalizer.
    art = normalize(clean)
    assert art.artifact_id == "jira-SSSB-1"
    assert art.team == "Atlas"


def test_jira_connector_uses_injected_fetcher():
    fake_issues = [
        {
            "key": "SSD-99",
            "summary": "x",
            "status": "To Do",
            "team": "Echo",
            "sprint": 15,
            "story_points": 1,
            "assignee": None,
            "reporter": "PM",
            "updated": "2026-05-21T09:00:00Z",
            "description": "",
            "comments": [],
        }
    ]
    conn = JiraConnector("SSD", fetcher=lambda project_key: fake_issues)
    artifacts = conn.fetch()
    assert list(artifacts) == ["jira-SSD-99"]
    assert artifacts["jira-SSD-99"].team == "Echo"


class _Resp:
    def __init__(self, successful=True, data=None, error=None):
        self.successful = successful
        self.data = data
        self.error = error


def test_issues_from_response_returns_issue_list():
    resp = _Resp(data={"issues": [{"key": "SSSB-1"}, {"key": "SSSB-2"}]})
    issues = _issues_from_response(resp)
    assert [i["key"] for i in issues] == ["SSSB-1", "SSSB-2"]


def test_issues_from_response_raises_on_failure():
    import pytest

    resp = _Resp(successful=False, error="boom")
    with pytest.raises(RuntimeError, match="boom"):
        _issues_from_response(resp)


def test_issues_from_response_empty_when_no_issues():
    assert _issues_from_response(_Resp(data={})) == []
    assert _issues_from_response(_Resp(data=None)) == []
