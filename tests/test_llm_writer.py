from sprintsight.evals.report import run_report_eval
from sprintsight.report.llm_writer import make_llm_writer


def _good_fake(system, user, schema):
    """Return clean one-line prose for every section key the schema requests."""
    keys = schema["properties"]["sections"]["properties"].keys()
    return {k: f"Narrative for {k}." for k in keys}


def test_llm_writer_greens_the_whole_suite():
    writer = make_llm_writer(complete=_good_fake)
    report = run_report_eval(writer)
    assert report.pass_rate == 1.0, report.summary()


def test_llm_writer_falls_back_on_ticket_id():
    # exec forbids ticket ids; a fake that injects one must be replaced by compose prose.
    def bad_fake(system, user, schema):
        keys = schema["properties"]["sections"]["properties"].keys()
        return {k: f"See ATLAS-12 for {k}." for k in keys}

    writer = make_llm_writer(complete=bad_fake)
    report = run_report_eval(writer)
    # exec case must still pass audience_fit because violating sections fell back.
    assert report.pass_rate == 1.0, report.summary()


def test_llm_writer_falls_back_when_over_cap():
    # A fake that floods exec past its 150-word cap triggers wholesale section fallback.
    def long_fake(system, user, schema):
        keys = schema["properties"]["sections"]["properties"].keys()
        return {k: ("word " * 200).strip() for k in keys}

    writer = make_llm_writer(complete=long_fake)
    report = run_report_eval(writer)
    assert report.pass_rate == 1.0, report.summary()


def test_thin_data_skips_the_llm():
    calls = []

    def spy(system, user, schema):
        calls.append(1)
        return {}

    from sprintsight.evals.fixtures import artifacts_for
    writer = make_llm_writer(complete=spy)
    rep = writer({"team": "Echo", "audience": "exec",
                  "artifacts": artifacts_for("Echo", [15])})
    assert rep.insufficient_evidence is True
    assert calls == []  # LLM never called on thin data
