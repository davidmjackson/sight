from sprintsight.evals.report import build_cases, null_writer, run_report_eval
from sprintsight.report.writer import compose


def test_cases_cover_the_spec():
    names = [c.name for c in build_cases()]
    assert names == ["boreas-exec", "atlas-programme", "echo-thin"]


def test_red_without_a_writer():
    # Eval-first: the null writer abstains, so the suite must not pass.
    report = run_report_eval(null_writer)
    assert report.pass_rate == 0.0
    # The audience-triple case is appended on top of the 3 build_cases().
    assert report.total == 4
    assert "boreas-exec" in report.summary()["failures"]
    assert "audience-triple" in report.summary()["failures"]


def test_compose_greens_citation_and_grounding():
    report = run_report_eval(compose)
    dims = report.dimension_rates()
    # Every claim cited, every citation valid, every numeric/status claim grounded.
    assert dims["citation_coverage"][0] == dims["citation_coverage"][1]
    assert dims["citation_validity"][0] == dims["citation_validity"][1]
    assert dims["grounding"][0] == dims["grounding"][1]
    # Required sections present for both audience cases.
    assert dims["required_sections"] == (2, 2)
