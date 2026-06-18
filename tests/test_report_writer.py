from sprintsight.detector import parse_metrics
from sprintsight.evals.fixtures import artifacts_for
from sprintsight.report.writer import _dependency_lines, _metric_claims, _risk_lines


def test_metric_claims_use_canonical_phrasing():
    arts = artifacts_for("Boreas", [15])
    m = parse_metrics(arts["burndown-boreas-s15"].body)
    texts = [c.text for c in _metric_claims(m, "burndown-boreas-s15")]
    assert "Committed 40 points." in texts
    assert "Completed 38 points." in texts
    assert "Carried over 1 stories." in texts
    assert "Velocity 38." in texts
    for c in _metric_claims(m, "burndown-boreas-s15"):
        assert c.citations == ["burndown-boreas-s15"]


def test_risk_lines_read_the_raid_descriptions_only():
    arts = artifacts_for("Atlas", [15])
    risks = _risk_lines(arts, "raid-atlas-s15")
    assert any("leave" in r.lower() for r in risks)
    # Risk text is the description column, never the R-A15-1 id column.
    assert all("R-A15-1" not in r for r in risks)


def test_dependency_lines_from_raid():
    arts = artifacts_for("Atlas", [15])
    deps = _dependency_lines(arts, "raid-atlas-s15")
    assert any("design system" in d.lower() for d in deps)
