import os

import pytest

from sprintsight.evals.calibration import anchors, run_calibration
from sprintsight.evals.judge import DIMENSIONS, JudgeScore


def _score(value: int) -> JudgeScore:
    return JudgeScore(scores={d: value for d in DIMENSIONS}, reasons={d: "" for d in DIMENSIONS})


def test_anchors_include_both_good_and_bad():
    labels = {a.should_pass for a in anchors()}
    assert labels == {True, False}, "calibration needs at least one good and one bad anchor"


def test_calibration_green_when_judge_agrees_with_labels():
    # Oracle judge: look up each anchor's known truth by report identity (run_calibration
    # passes the same Report object straight through to the judge).
    truth = {id(a.report): a.should_pass for a in anchors()}

    def oracle(report, audience):
        return _score(5) if truth[id(report)] else _score(1)

    report = run_calibration(oracle)
    assert report.pass_rate == 1.0, report.summary()


def test_calibration_fails_when_judge_cannot_separate_good_from_bad():
    # A blind judge that passes everything must fail calibration on the bad anchors.
    def blind(report, audience):
        return _score(5)

    report = run_calibration(blind)
    assert report.pass_rate < 1.0


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-")
    or len(os.getenv("ANTHROPIC_API_KEY", "")) < 50,
    reason="no real Anthropic key wired",
)
def test_live_judge_passes_calibration():
    from sprintsight.evals.judge import make_judge

    report = run_calibration(make_judge())
    assert report.pass_rate == 1.0, report.summary()
