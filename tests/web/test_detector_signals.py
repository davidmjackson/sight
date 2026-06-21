from sprintsight.detector import detect
from sprintsight.evals.fixtures import artifacts_for


def test_detect_exposes_signals_for_atlas():
    arts = artifacts_for("Atlas", [14, 15])
    verdict = detect({"team": "Atlas", "artifacts": arts})
    assert isinstance(verdict.signals, list)
    assert verdict.signals, "expected non-empty signals"
    assert any("burn ratio" in s for s in verdict.signals)
