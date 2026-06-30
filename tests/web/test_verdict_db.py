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
