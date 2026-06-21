"""Watermelon detection eval (SS-2.3 / SS-1.4).

Implements docs/evals/watermelon-eval.md on top of the generic harness. Builds one case
per team (Atlas/Boreas/Cygnus/Draco), judged as-of Sprint 15 with Sprint 14 as context,
from the SS-2.1 corpus fixtures. Grading is deterministic and dual-gated per the spec:

  * classification: is_watermelon AND actual_status must equal the ground truth, and
  * evidence: every required artifact_id must appear in the verdict's evidence list.

A case passes only when BOTH gates pass (right label + missing evidence = FAIL).

The subject under test is a *detector*: `detect(inputs) -> Verdict`. The real detector
is SS-2.7; until then `null_detector` abstains, so the suite is RED by design — that is
the eval-first signal that the gate bites before any feature code exists.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sprintsight.evals.fixtures import artifacts_for, load_ground_truth
from sprintsight.evals.harness import Assertion, Case, SuiteReport, run_suite

TEAMS = ["Atlas", "Boreas", "Cygnus", "Draco"]
JUDGED_AS_OF_SPRINT = 15
CONTEXT_SPRINTS = [14, 15]


@dataclass
class Verdict:
    """The SS-1.4 detector output contract (section 2)."""

    team: str
    reported_status: str
    actual_status: str
    is_watermelon: bool
    evidence: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    explanation: str = ""


# A detector consumes {"team": str, "artifacts": dict[str, Artifact]} and returns a Verdict.
Detector = Callable[[dict[str, Any]], Verdict]

# An assertion check over a verdict.
Check = Callable[[Verdict], Assertion]


def null_detector(inputs: dict[str, Any]) -> Verdict:
    """Placeholder until SS-2.7. Abstains, so every case fails the evidence gate (RED)."""
    return Verdict(
        team=inputs["team"],
        reported_status="unknown",
        actual_status="unknown",
        is_watermelon=False,
        evidence=[],
        explanation="no detector implemented yet (SS-2.7)",
    )


def _classification(expected_watermelon: bool, expected_actual: str) -> Check:
    def check(v: Verdict) -> Assertion:
        ok = v.is_watermelon == expected_watermelon and v.actual_status == expected_actual
        return Assertion(
            "classification",
            ok,
            f"is_watermelon={v.is_watermelon} (want {expected_watermelon}), "
            f"actual={v.actual_status} (want {expected_actual})",
        )

    return check


def _evidence(required: set[str]) -> Check:
    def check(v: Verdict) -> Assertion:
        missing = required - set(v.evidence)
        return Assertion(
            "evidence",
            not missing,
            f"missing={sorted(missing)}" if missing else "all required evidence cited",
        )

    return check


def _s15_record(team: str) -> dict[str, Any]:
    gt = load_ground_truth()
    return next(
        r for r in gt["records"] if r["team"] == team and r["sprint"] == JUDGED_AS_OF_SPRINT
    )


def build_cases() -> list[Case]:
    """One case per team, judged as-of Sprint 15 with Sprint 14 as context."""
    cases: list[Case] = []
    for team in TEAMS:
        record = _s15_record(team)
        cases.append(
            Case(
                name=team.lower(),
                inputs={"team": team, "artifacts": artifacts_for(team, CONTEXT_SPRINTS)},
                assertions=[
                    _classification(record["is_watermelon"], record["actual_status"]),
                    _evidence(set(record["expected_evidence"])),
                ],
            )
        )
    return cases


def run_watermelon_eval(detector: Detector | None = None) -> SuiteReport:
    """Run the 4-case watermelon suite against `detector` (defaults to the null detector)."""
    return run_suite(build_cases(), detector or null_detector)
