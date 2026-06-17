"""Generic deterministic eval harness.

A *subject under test* is any callable `subject(inputs) -> output`. A `Case` pairs the
inputs with a list of named assertions over the output. `run_suite` runs every case,
applies its assertions, and returns a `SuiteReport` that scores both overall pass rate
and per-dimension rates (e.g. "classification" vs "evidence" for the watermelon eval).

Deterministic by construction: assertions are plain predicates, no LLM judging here.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sprintsight.evals.tracing import Tracer, get_tracer

# An assertion checker takes the subject's output and returns a pass/fail with detail.
AssertionFn = Callable[[Any], "Assertion"]
Subject = Callable[[Any], Any]


@dataclass(frozen=True)
class Assertion:
    """One named check against a subject's output.

    `name` is the scoring dimension (e.g. "classification", "evidence"); reusing a name
    across cases lets the suite report a per-dimension rate.
    """

    name: str
    passed: bool
    detail: str = ""


@dataclass
class Case:
    """One eval case: inputs for the subject plus the assertions its output must satisfy."""

    name: str
    inputs: Any
    assertions: list[AssertionFn] = field(default_factory=list)


@dataclass
class CaseResult:
    name: str
    passed: bool
    assertions: list[Assertion]
    error: str | None = None


@dataclass
class SuiteReport:
    """Scored result of a suite run."""

    results: list[CaseResult]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def dimension_rates(self) -> dict[str, tuple[int, int]]:
        """Per-assertion-name (passed, total), e.g. {"classification": (4, 4)}."""
        rates: dict[str, list[int]] = {}
        for result in self.results:
            for a in result.assertions:
                bucket = rates.setdefault(a.name, [0, 0])
                bucket[1] += 1
                if a.passed:
                    bucket[0] += 1
        return {name: (p, t) for name, (p, t) in rates.items()}

    def summary(self) -> dict[str, Any]:
        """JSON-friendly scoring summary, shaped for the eval specs."""
        return {
            "cases": self.total,
            "passed": self.passed,
            "pass_rate": round(self.pass_rate, 4),
            "dimensions": {
                name: {"passed": p, "total": t}
                for name, (p, t) in self.dimension_rates().items()
            },
            "failures": [r.name for r in self.results if not r.passed],
        }


def run_suite(cases: list[Case], subject: Subject, tracer: Tracer | None = None) -> SuiteReport:
    """Run every case through `subject` and score the results.

    A case passes only when all of its assertions pass. An exception from the subject or
    an assertion fails that case (recorded in `error`) rather than aborting the suite.
    """
    tracer = tracer or get_tracer()
    results: list[CaseResult] = []

    for case in cases:
        with tracer.span(f"case:{case.name}"):
            try:
                output = subject(case.inputs)
                checks = [check(output) for check in case.assertions]
                results.append(
                    CaseResult(
                        name=case.name,
                        passed=all(c.passed for c in checks),
                        assertions=checks,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - a bad case must not kill the suite
                results.append(
                    CaseResult(name=case.name, passed=False, assertions=[], error=repr(exc))
                )

    return SuiteReport(results=results)
