"""Parity guard for the verdict-off-DB slice: rebuilding artifacts from only the columns the
DB stores (dropping `meta`) must not change the detector verdict or the composed report."""

import pytest

from sprintsight.detector import detect
from sprintsight.evals.fixtures import Artifact, artifacts_for
from sprintsight.report.writer import compose
from sprintsight.web.service import TEAMS

_SPRINTS = [14, 15]
_AUDIENCES = ("exec", "programme", "team")


def db_shaped(arts: dict[str, Artifact]) -> dict[str, Artifact]:
    """Simulate a DB round-trip: only the five persisted fields survive; `meta` is dropped.
    Mirrors exactly what PostgresArtifactSource rebuilds (Task 3)."""
    return {
        aid: Artifact(
            artifact_id=a.artifact_id,
            source_type=a.source_type,
            team=a.team,
            sprint=a.sprint,
            meta={},
            body=a.body,
        )
        for aid, a in arts.items()
    }


def _verdict_outcome(team, arts):
    """Capture the verdict OR the exception type, so teams with thin data (Echo) compare equal
    on both paths whatever detect() does."""
    try:
        return ("ok", detect({"team": team, "artifacts": arts}))
    except Exception as exc:  # noqa: BLE001 - we are comparing failure modes too
        return ("error", type(exc).__name__)


@pytest.mark.parametrize("team", TEAMS)
def test_verdict_parity(team):
    corpus = artifacts_for(team, _SPRINTS)
    rebuilt = db_shaped(corpus)
    assert _verdict_outcome(team, rebuilt) == _verdict_outcome(team, corpus)


@pytest.mark.parametrize("team", TEAMS)
@pytest.mark.parametrize("audience", _AUDIENCES)
def test_report_parity(team, audience):
    corpus = artifacts_for(team, _SPRINTS)
    rebuilt = db_shaped(corpus)
    got = compose({"team": team, "audience": audience, "artifacts": rebuilt})
    want = compose({"team": team, "audience": audience, "artifacts": corpus})
    assert got == want
