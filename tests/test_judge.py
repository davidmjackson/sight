# tests/test_judge.py
import os

import pytest

from sprintsight.evals.judge import DIMENSIONS, _anthropic_grader, make_judge
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


def test_judge_fails_bar_when_mean_below_four_even_if_each_at_least_three():
    score = make_judge(grade=_fake_grader({d: 3 for d in DIMENSIONS}))(_report(), "exec")
    # every dimension == 3 (>= MIN_PER_DIMENSION) but mean 3.0 < MIN_MEAN 4.0
    assert score.passes is False


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
