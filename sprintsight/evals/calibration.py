"""Calibration meta-eval: grade the judge before trusting it (Stage 4, SS-7, spec section 4).

A small set of hand-labelled anchor reports. We assert the judge scores the clearly-good
anchors as passing and the clearly-bad anchors as below-bar. If the judge cannot separate
obvious good from obvious bad, it is not trustworthy and must not gate. Same pattern as every
eval: known truth, scored. Anchors are hand-authored fixtures, independent of the live writer,
so the calibration is stable across writer changes.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sprintsight.evals.harness import Assertion, Case, SuiteReport, run_suite
from sprintsight.evals.judge import JudgeFn, JudgeScore
from sprintsight.report.contract import Report

_GOOD_EXEC = Report(
    team="Boreas",
    audience="exec",
    sections={
        "overall RAG": (
            "Green. Sprint 15 closed on plan and the 30 June release date is firm, with "
            "delivery confidence high and trending up."
        ),
        "top 3 risks": (
            "The one risk worth your attention is a vendor API change that could slip "
            "integration by a week. A workaround is in flight, with a fallback ready if it "
            "lands late. Two smaller risks, test-environment capacity and a pending design "
            "sign-off, are already contained."
        ),
        "ask/decision needed": (
            "One decision needed: approve a second reviewer for two weeks. That single step "
            "removes the only credible threat to the release date, with no impact on other teams."
        ),
    },
)

_WAFFLY_EXEC = Report(
    team="Boreas",
    audience="exec",
    sections={
        "overall RAG": (
            "At this moment in time it could broadly be said that, on balance and all things "
            "considered, the overall directional posture of the workstream remains in a state "
            "that is arguably not inconsistent with a generally positive trajectory, subject to "
            "the usual caveats and the evolving nature of the broader delivery landscape."
        ),
        "top 3 risks": "Various items of a risk-shaped nature may or may not require attention.",
        "ask/decision needed": "Continue to monitor and revisit as appropriate in due course.",
    },
)

_JARGON_EXEC = Report(
    team="Atlas",
    audience="exec",
    sections={
        "overall RAG": (
            "Amber: WIP over the cap, burndown flat, carry-over spiking on the s15 board."
        ),
        "top 3 risks": (
            "Blocked tickets in the sprint backlog; velocity dipped below the rolling mean."
        ),
        "ask/decision needed": "Re-baseline the story-point commitment for the next iteration.",
    },
)

_VAGUE_ASK_EXEC = Report(
    team="Boreas",
    audience="exec",
    sections={
        "overall RAG": "Green and on track.",
        "top 3 risks": "A dependency risk and a couple of smaller risks.",
        "ask/decision needed": "Some support from leadership would be helpful at some point.",
    },
)


@dataclass(frozen=True)
class Anchor:
    """One calibration anchor: a report plus the known truth about its prose quality."""

    name: str
    report: Report
    audience: str
    should_pass: bool  # the hand-assigned truth: is this report's prose acceptable?


def anchors() -> list[Anchor]:
    """Hand-labelled good/bad reports the judge must rank correctly to be trusted."""
    return [
        Anchor("good-exec", _GOOD_EXEC, "exec", True),
        Anchor("waffly-exec", _WAFFLY_EXEC, "exec", False),
        Anchor("jargon-exec", _JARGON_EXEC, "exec", False),
        Anchor("vague-ask-exec", _VAGUE_ASK_EXEC, "exec", False),
    ]


def _expectation(anchor: Anchor) -> Callable[[JudgeScore], Assertion]:
    def check(score: JudgeScore) -> Assertion:
        ok = score.passes == anchor.should_pass
        return Assertion(
            "calibration",
            ok,
            f"{anchor.name}: judge passes={score.passes}, expected {anchor.should_pass} "
            f"(scores={score.scores})",
        )

    return check


def run_calibration(judge: JudgeFn) -> SuiteReport:
    """Run every anchor through `judge` and assert it matches the anchor's known truth."""
    cases = [Case(name=a.name, inputs=a, assertions=[_expectation(a)]) for a in anchors()]

    def subject(anchor: Anchor) -> JudgeScore:
        return judge(anchor.report, anchor.audience)

    return run_suite(cases, subject)
