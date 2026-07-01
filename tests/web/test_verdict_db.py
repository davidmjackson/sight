"""Gating + fail-safe wiring for verdict/report off the DB."""

import sprintsight.web.service as svc
from sprintsight.evals.fixtures import Artifact


class _FakeSource:
    def __init__(self, arts):
        self._arts = arts
        self.closed = False

    def artifacts_for(self, team, sprints=None):
        return self._arts

    def close(self):
        self.closed = True


def _one_atlas_artifact():
    return {
        "status-atlas-s15": Artifact(
            artifact_id="status-atlas-s15", source_type="confluence", team="Atlas",
            sprint=15, meta={}, body="Overall status: green",
        )
    }


def test_gate_off_uses_corpus(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_VERDICT_DB", raising=False)
    arts = svc._artifacts_for("Atlas")
    # corpus has the real multi-artifact set, not our single fake
    assert "burndown-atlas-s15" in arts


def test_gate_on_uses_db_source(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_VERDICT_DB", "on")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    fake = _FakeSource(_one_atlas_artifact())
    monkeypatch.setattr(svc, "_make_artifact_source", lambda: fake)
    arts = svc._artifacts_for("Atlas")
    assert set(arts) == {"status-atlas-s15"}
    assert fake.closed is True


def test_db_error_falls_back_to_corpus(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_VERDICT_DB", "on")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(svc, "_make_artifact_source", _boom)
    arts = svc._artifacts_for("Atlas")
    assert "burndown-atlas-s15" in arts  # corpus fallback


def test_empty_db_falls_back_to_corpus(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_VERDICT_DB", "on")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setattr(svc, "_make_artifact_source", lambda: _FakeSource({}))
    arts = svc._artifacts_for("Atlas")
    assert "burndown-atlas-s15" in arts  # un-backfilled DB -> corpus


def test_team_detail_fetches_consumer_artifacts_once(monkeypatch):
    """team_detail derives the verdict, report, and evidence from a SINGLE consumer fetch.
    A second fetch for the PROVIDER team (cross-team risk reconciliation) is expected and
    distinct; the consumer team must never be fetched more than once."""
    real = svc._artifacts_for
    calls: list[str] = []

    def _counting(team):
        calls.append(team)
        return real(team)

    monkeypatch.setattr(svc, "_artifacts_for", _counting)
    detail = svc.team_detail("atlas")
    assert detail is not None and detail.has_verdict
    assert calls.count("Atlas") == 1  # consumer fetched exactly once
    # provider team may also be fetched once for cross-team reconciliation
    assert len(calls) == calls.count("Atlas") + calls.count("Draco")


def test_team_detail_with_gate_on_makes_one_db_round_trip_per_team(monkeypatch):
    """With the verdict-DB gate ON, team_detail builds the DB artifact source once per unique
    team: once for the consumer (Atlas) and once for the provider (Draco) during cross-team
    risk reconciliation. Two builds total, one per team, not duplicate fetches of the same team."""
    monkeypatch.setenv("SPRINTSIGHT_VERDICT_DB", "on")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    built: list[int] = []

    def _make():
        built.append(1)
        return _FakeSource(svc.artifacts_for("Atlas", svc._SPRINTS))  # full set -> verdict

    monkeypatch.setattr(svc, "_make_artifact_source", _make)
    detail = svc.team_detail("atlas")
    assert detail is not None and detail.has_verdict
    assert len(built) == 2  # one for consumer (Atlas), one for provider (Draco)
