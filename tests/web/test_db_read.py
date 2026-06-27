"""Slice 4 — web reads cited evidence FROM the DB, behind a fail-safe gate.

Eval-first served-data tests. They run fully offline by injecting a FAKE retriever into the
`service._make_retriever` seam, so no real database is ever touched. They pin: the gate logic,
team-scoping (the fake records the `team` it was queried with), the chunk->KnowledgeItem mapping,
and the fail-safe (a retriever that raises yields an empty panel, never an exception).
"""

import pytest
from fastapi.testclient import TestClient

from sprintsight.retrieval.retriever import RetrievedChunk
from sprintsight.web import service
from sprintsight.web.app import create_app

from .conftest import ADMIN, login


class FakeRetriever:
    """Records the search args and returns canned chunks; never touches a DB."""

    def __init__(self, chunks: list[RetrievedChunk] | None = None) -> None:
        self._chunks = chunks if chunks is not None else _sample_chunks()
        self.calls: list[dict] = []
        self.closed = False

    def search(self, query, embedder, k=5, team=None):
        self.calls.append({"query": query, "k": k, "team": team})
        return list(self._chunks)

    def close(self):
        self.closed = True


class RaisingRetriever:
    def __init__(self) -> None:
        self.closed = False

    def search(self, *a, **k):
        raise RuntimeError("DB unreachable")

    def close(self):
        self.closed = True


def _sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            artifact_id="",
            source_type="confluence",
            source_ref="ATLAS-STATUS-S15",
            team="Atlas",
            sprint=0,
            ordinal=0,
            text="Overall status green. Auth integration on track.\nMore detail follows.",
            score=0.91,
        ),
        RetrievedChunk(
            artifact_id="",
            source_type="jira",
            source_ref="ATLAS-BURNDOWN-S15",
            team="Atlas",
            sprint=0,
            ordinal=0,
            text="Committed 40, completed 18.",
            score=0.77,
        ),
    ]


@pytest.fixture
def db_on(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_WEB_DB", "on")
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub/db")


# --- gate logic ---------------------------------------------------------------

def test_db_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_DB", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub/db")
    assert service._db_enabled() is False


def test_db_flag_on_but_no_dsn_stays_off(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_WEB_DB", "on")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert service._db_enabled() is False


def test_db_dsn_present_but_flag_off_stays_off(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_DB", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub/db")
    assert service._db_enabled() is False


def test_db_enabled_needs_flag_and_dsn(db_on):
    assert service._db_enabled() is True


# --- reader behaviour (offline via injected fake) -----------------------------

def test_db_knowledge_empty_when_gate_off(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_DB", raising=False)
    fake = FakeRetriever()
    monkeypatch.setattr(service, "_make_retriever", lambda: fake)
    assert service.db_knowledge_for("Atlas") == []
    assert fake.calls == []  # gate short-circuits before any DB call


def test_db_knowledge_is_team_scoped(db_on, monkeypatch):
    fake = FakeRetriever()
    monkeypatch.setattr(service, "_make_retriever", lambda: fake)
    items = service.db_knowledge_for("Atlas")
    assert len(items) == 2
    assert fake.calls[0]["team"] == "Atlas"  # slice-3 team_id scoping is exercised
    assert fake.closed is True


def test_db_knowledge_maps_chunk_fields(db_on, monkeypatch):
    fake = FakeRetriever()
    monkeypatch.setattr(service, "_make_retriever", lambda: fake)
    first = service.db_knowledge_for("Atlas")[0]
    assert first.source_type == "confluence"
    assert first.source_ref == "ATLAS-STATUS-S15"
    assert first.snippet == "Overall status green. Auth integration on track."
    assert first.score == pytest.approx(0.91, abs=0.01)


def test_db_knowledge_failsafe_on_error(db_on, monkeypatch):
    raising = RaisingRetriever()
    monkeypatch.setattr(service, "_make_retriever", lambda: raising)
    assert service.db_knowledge_for("Atlas") == []  # no exception escapes
    assert raising.closed is True  # connection still released


def test_db_knowledge_failsafe_on_connect_error(db_on, monkeypatch):
    """The realistic live failure: building the retriever itself raises (DB down / bad creds)."""

    def boom():
        raise RuntimeError("could not connect")

    monkeypatch.setattr(service, "_make_retriever", boom)
    assert service.db_knowledge_for("Atlas") == []  # no exception escapes, no leak (nothing opened)


# --- wired into team_detail ---------------------------------------------------

def test_team_detail_has_no_db_knowledge_when_off(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_DB", raising=False)
    detail = service.team_detail("atlas")
    assert detail is not None
    assert detail.db_knowledge == []


def test_team_detail_populates_db_knowledge_when_on(db_on, monkeypatch):
    fake = FakeRetriever()
    monkeypatch.setattr(service, "_make_retriever", lambda: fake)
    detail = service.team_detail("atlas")
    assert detail is not None
    assert [i.source_ref for i in detail.db_knowledge] == [
        "ATLAS-STATUS-S15",
        "ATLAS-BURNDOWN-S15",
    ]
    assert fake.calls[0]["team"] == "Atlas"


# --- rendered page + JSON API -------------------------------------------------

def test_team_page_shows_db_panel_when_on(db_on, monkeypatch):
    monkeypatch.setattr(service, "_make_retriever", lambda: FakeRetriever())
    client = login(TestClient(create_app()), ADMIN)
    html = client.get("/team/atlas").text
    assert "From the knowledge base" in html
    assert "ATLAS-STATUS-S15" in html


def test_team_page_omits_db_panel_when_off(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_DB", raising=False)
    client = login(TestClient(create_app()), ADMIN)
    html = client.get("/team/atlas").text
    assert "From the knowledge base" not in html


def test_api_team_carries_db_knowledge(db_on, monkeypatch):
    monkeypatch.setattr(service, "_make_retriever", lambda: FakeRetriever())
    client = login(TestClient(create_app()), ADMIN)
    body = client.get("/api/team/atlas").json()
    assert [k["source_ref"] for k in body["db_knowledge"]] == [
        "ATLAS-STATUS-S15",
        "ATLAS-BURNDOWN-S15",
    ]
