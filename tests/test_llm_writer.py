import os

import pytest

from sprintsight.evals.report import run_report_eval
from sprintsight.report.llm_writer import _anthropic_completer, make_llm_writer


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


def test_anthropic_completer_constructs_without_calling_api():
    # Building the completer must not require a network call.
    completer = _anthropic_completer("claude-sonnet-4-6")
    assert callable(completer)


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-")
    or len(os.getenv("ANTHROPIC_API_KEY", "")) < 50,
    reason="no real Anthropic key wired",
)
def test_live_llm_writer_greens_the_suite():
    from sprintsight.evals.report import run_report_eval
    report = run_report_eval(make_llm_writer())
    assert report.pass_rate == 1.0, report.summary()


def test_system_prompt_carries_the_readability_directives():
    from sprintsight.report.llm_writer import _SYSTEM

    s = _SYSTEM.lower()
    assert "the one to watch" in s  # lead-with-first-item framing
    assert "watch-point" in s  # grounded watch-point directive
    # the banned-passive marker (in directive + exemplar)
    assert "alignment will be maintained" in s
    assert "trajectory and decision" in s  # programme register directive
    # Bright line: never instruct a severity ranking.
    for banned in ("highest", "most severe", "biggest"):
        assert banned in s, f"directive must explicitly forbid '{banned}'"


def test_user_prompt_names_the_lead_item():
    from sprintsight.report.audience import PROFILES
    from sprintsight.report.llm_writer import _user_prompt
    from sprintsight.report.writer import Facts

    f = Facts(
        team="Boreas", audience="exec", profile=PROFILES["exec"],
        burndown_id="b", status_id="s", raid_id="r", metrics=None,
        rag="green", rag_cite="s",
        risks=["First risk.", "Second risk."], deps=[], looking_ahead="",
        claims=[], insufficient=False,
    )
    assert "first risk listed is your lead item" in _user_prompt(f).lower()
