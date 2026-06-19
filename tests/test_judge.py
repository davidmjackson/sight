# tests/test_judge.py
import os

import pytest

from sprintsight.evals.judge import DIMENSIONS, _anthropic_grader, make_judge, sample_judge
from sprintsight.report.contract import Report


def _report(audience: str = "exec") -> Report:
    return Report(
        team="Boreas",
        audience=audience,
        sections={
            "overall RAG": "On track and green.",
            "ask/decision needed": "Approve one reviewer.",
        },
    )


def _fake_grader(scores: dict[str, int]):
    def grade(system, user, schema):
        return {d: {"score": scores[d], "reason": f"r-{d}"} for d in scores}
    return grade


def test_judge_returns_structured_scores_and_reasons():
    judge = make_judge(grade=_fake_grader({d: 5 for d in DIMENSIONS}))
    score = judge(_report(), "exec")
    assert score.scores == {d: 5 for d in DIMENSIONS}
    assert set(score.reasons) == set(DIMENSIONS)
    assert score.mean == 5.0
    assert score.passes is True


def test_judge_fails_bar_when_one_dimension_low():
    bad = {d: 5 for d in DIMENSIONS}
    bad["clarity"] = 2
    score = make_judge(grade=_fake_grader(bad))(_report(), "exec")
    assert score.passes is False


def test_judge_fails_bar_when_mean_below_bar_even_if_each_at_least_three():
    score = make_judge(grade=_fake_grader({d: 3 for d in DIMENSIONS}))(_report(), "exec")
    # every dimension == 3 (>= MIN_PER_DIMENSION) but mean 3.0 < MIN_MEAN 3.5
    assert score.passes is False


def test_judge_passes_strong_report_with_one_middling_dimension():
    # The good-exec calibration shape: 4/4/3/4, mean 3.75. A strong report with one
    # merely-fine dimension must clear the tuned bar (every dim >= 3 AND mean >= 3.5).
    # Guards against MIN_MEAN drifting back up and failing a genuinely good report.
    scores = {d: 4 for d in DIMENSIONS}
    scores["coherence"] = 3
    score = make_judge(grade=_fake_grader(scores))(_report(), "exec")
    assert score.mean == 3.75
    assert score.passes is True


def test_judge_handles_missing_dimension_as_failing():
    def partial_grader(system, user, schema):
        return {"clarity": {"score": 5, "reason": "ok"}}  # other three missing
    score = make_judge(grade=partial_grader)(_report(), "exec")
    assert score.scores["audience_fit"] == 0
    assert score.passes is False


def test_anthropic_grader_constructs_without_calling_api():
    assert callable(_anthropic_grader("claude-sonnet-4-6"))


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-")
    or len(os.getenv("ANTHROPIC_API_KEY", "")) < 50,
    reason="no real Anthropic key wired",
)
def test_live_judge_scores_a_clean_report_highly():
    score = make_judge()(_report(), "exec")
    assert score.mean >= 3.0, score.scores


def test_judge_prompt_uses_human_headings_not_raw_keys():
    captured = {}

    def grader(system, user, schema):
        captured["user"] = user
        return {d: {"score": 4, "reason": "x"} for d in DIMENSIONS}

    report = Report(team="Boreas", audience="exec",
                    sections={"overall_rag": "Green.", "ask": "No decision."})
    make_judge(grade=grader)(report, "exec")
    assert "## Overall status" in captured["user"]
    assert "overall_rag" not in captured["user"]


def _sequencing_grader(seq_by_dim: dict[str, list[int]]):
    """Fake grader that returns a different score per call, walking each dimension's list."""
    state = {"i": 0}

    def grade(system, user, schema):
        i = state["i"]
        state["i"] += 1
        return {d: {"score": seq_by_dim[d][i], "reason": f"r{i}-{d}"} for d in seq_by_dim}

    return grade


def test_sample_judge_takes_per_dimension_median():
    # clarity samples [2,4,4] -> median 4; every other dim constant at 4.
    seq = {d: [4, 4, 4] for d in DIMENSIONS}
    seq["clarity"] = [2, 4, 4]
    judge = make_judge(grade=_sequencing_grader(seq))
    score = sample_judge(judge, _report(), "exec", n=3)
    assert score.scores["clarity"] == 4
    assert score.scores["audience_fit"] == 4
    assert score.mean == 4.0


def test_sample_judge_single_sample_equals_one_run():
    seq = {d: [3] for d in DIMENSIONS}
    judge = make_judge(grade=_sequencing_grader(seq))
    score = sample_judge(judge, _report(), "exec", n=1)
    assert score.scores == {d: 3 for d in DIMENSIONS}


def test_sample_judge_drops_failed_samples():
    calls = {"i": 0}

    def flaky(system, user, schema):
        calls["i"] += 1
        if calls["i"] == 2:  # second call blows up; it must be dropped, not fatal
            raise RuntimeError("boom")
        return {d: {"score": 4, "reason": "ok"} for d in DIMENSIONS}

    score = sample_judge(make_judge(grade=flaky), _report(), "exec", n=3)
    assert score.scores == {d: 4 for d in DIMENSIONS}


def test_sample_judge_raises_when_all_samples_fail():
    import pytest as _pytest

    def always_fails(system, user, schema):
        raise RuntimeError("boom")

    with _pytest.raises(RuntimeError):
        sample_judge(make_judge(grade=always_fails), _report(), "exec", n=3)
