"""SS-2.2: the generic eval harness scores correctly on a stub suite."""

from sprintsight.evals import Assertion, Case, run_suite


def _classification(expected: str):
    return lambda out: Assertion("classification", out["label"] == expected, f"got {out['label']}")


def _evidence(required: set[str]):
    return lambda out: Assertion("evidence", required <= set(out["evidence"]), "evidence subset")


def _subject(inputs):
    """Stub subject under test: just echoes a canned verdict from the inputs."""
    return {"label": inputs["label"], "evidence": inputs["evidence"]}


def test_all_pass():
    cases = [
        Case(
            name="atlas",
            inputs={"label": "watermelon", "evidence": ["a", "b"]},
            assertions=[_classification("watermelon"), _evidence({"a", "b"})],
        ),
        Case(
            name="boreas",
            inputs={"label": "green", "evidence": ["c"]},
            assertions=[_classification("green"), _evidence({"c"})],
        ),
    ]
    report = run_suite(cases, _subject)

    assert report.total == 2
    assert report.passed == 2
    assert report.pass_rate == 1.0
    assert report.dimension_rates() == {"classification": (2, 2), "evidence": (2, 2)}


def test_evidence_gate_fails_lucky_guess():
    # Right label but missing required evidence must fail the case (the evidence gate).
    case = Case(
        name="lucky",
        inputs={"label": "watermelon", "evidence": []},
        assertions=[_classification("watermelon"), _evidence({"must-cite"})],
    )
    report = run_suite([case], _subject)

    assert report.passed == 0
    assert report.dimension_rates() == {"classification": (1, 1), "evidence": (0, 1)}
    assert report.summary()["failures"] == ["lucky"]


def test_subject_exception_is_isolated():
    def boom(_):
        raise RuntimeError("subject blew up")

    report = run_suite([Case(name="explodes", inputs=None)], boom)

    assert report.passed == 0
    assert report.results[0].error is not None
