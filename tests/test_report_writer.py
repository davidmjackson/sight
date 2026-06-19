from sprintsight.detector import parse_metrics
from sprintsight.evals.fixtures import artifacts_for
from sprintsight.report.writer import (
    _compose_sections,
    _dependency_lines,
    _grounded_facts,
    _metric_claims,
    _risk_lines,
)


def test_grounded_facts_boreas_exec():
    f = _grounded_facts(
        {"team": "Boreas", "audience": "exec", "artifacts": artifacts_for("Boreas", [15])}
    )
    assert f.insufficient is False
    assert f.rag == "green"
    assert f.rag_cite == "status-boreas-s15"
    # claims are deterministic: RAG claim is always first and cited.
    assert f.claims[0].text == "Overall status: green."
    assert f.claims[0].citations == ["status-boreas-s15"]


def test_grounded_facts_echo_is_insufficient():
    f = _grounded_facts(
        {"team": "Echo", "audience": "exec", "artifacts": artifacts_for("Echo", [15])}
    )
    assert f.insufficient is True
    assert f.claims == []


def test_compose_sections_exec_keys():
    f = _grounded_facts(
        {"team": "Boreas", "audience": "exec", "artifacts": artifacts_for("Boreas", [15])}
    )
    sections = _compose_sections(f)
    assert set(sections) == {"overall_rag", "top_risks", "ask"}


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


def test_top_risks_render_each_risk_on_its_own_line():
    from sprintsight.report.writer import _compose_sections, _grounded_facts
    f = _grounded_facts(
        {"team": "Boreas", "audience": "exec", "artifacts": artifacts_for("Boreas", [15])}
    )
    s = _compose_sections(f)
    lines = [ln for ln in s["top_risks"].splitlines() if ln.strip()]
    assert len(lines) >= 2, "Boreas exec has multiple risks; they must not run together"
    assert all(ln.startswith("- ") for ln in lines), "each risk is its own bullet"
