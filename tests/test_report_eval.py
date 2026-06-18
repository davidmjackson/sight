from sprintsight.evals.report import build_cases, null_writer, run_report_eval


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
