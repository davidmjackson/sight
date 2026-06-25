"""Cross-tool watermelon eval (Goal B, SS-5).

Implements docs/evals/cross-tool-watermelon-eval.md on the generic harness. Five per-ticket
cases pairing a Jira status with GitHub Activity, dual-gated (classification + evidence) like
the team watermelon eval. Subject under test: a reconciler `reconcile(inputs) -> Verdict`.
Until SS-5's reconcile exists, `null_reconciler` abstains, so the suite is RED by design.
"""

from collections.abc import Callable
from typing import Any

from sprintsight.connect.github import PR, Activity
from sprintsight.evals.harness import Assertion, Case, SuiteReport, run_suite
from sprintsight.evals.watermelon import Verdict

Reconciler = Callable[[dict[str, Any]], Verdict]
Check = Callable[[Verdict], Assertion]

AS_OF = "2026-06-25T00:00:00+00:00"


def _act(key: str, **kw: Any) -> Activity:
    return Activity(
        key=key,
        has_branch=kw.get("has_branch", False),
        prs=kw.get("prs", []),
        commit_count=kw.get("commit_count", 0),
        last_commit_at=kw.get("last_commit_at"),
    )


CASES: list[dict[str, Any]] = [
    {
        "name": "case1",
        "ticket": {"key": "SSSB-1", "status": "In Progress", "team": "Atlas"},
        "activity": None,
        "is_watermelon": True,
        "actual": "red",
        "required_evidence": {"jira-SSSB-1", "github:no-ref:SSSB-1"},
    },
    {
        "name": "case2",
        "ticket": {"key": "SSSB-2", "status": "Done", "team": "Atlas"},
        "activity": _act(
            "SSSB-2",
            prs=[PR(number=12, state="open", merged=False, title="SSSB-2", url="u")],
        ),
        "is_watermelon": True,
        "actual": "red",
        "required_evidence": {"jira-SSSB-2", "github:PR#12:open-unmerged"},
    },
    {
        "name": "case3",
        "ticket": {"key": "SSSB-3", "status": "In Progress", "team": "Boreas"},
        "activity": _act(
            "SSSB-3",
            prs=[PR(number=5, state="open", merged=False, title="SSSB-3", url="u")],
            commit_count=3,
        ),
        "is_watermelon": False,
        "actual": "green",
        "required_evidence": set(),
    },
    {
        "name": "case4",
        "ticket": {"key": "SSSB-4", "status": "Done", "team": "Boreas"},
        "activity": _act(
            "SSSB-4",
            prs=[PR(number=8, state="closed", merged=True, title="SSSB-4", url="u")],
        ),
        "is_watermelon": False,
        "actual": "green",
        "required_evidence": set(),
    },
    {
        "name": "case5",
        "ticket": {"key": "SSSB-5", "status": "To Do", "team": "Cygnus"},
        "activity": None,
        "is_watermelon": False,
        "actual": "green",
        "required_evidence": set(),
    },
    {
        "name": "case6",
        "ticket": {"key": "SSSB-7", "status": "In Progress", "team": "Atlas"},
        "activity": _act(
            "SSSB-7",
            prs=[PR(number=20, state="open", merged=False, title="SSSB-7",
                    url="u", updated_at="2026-06-15T00:00:00Z")],
        ),
        "as_of": AS_OF,
        "is_watermelon": False,
        "actual": "amber",
        "required_evidence": {"jira-SSSB-7", "github:PR#20:stalled-10d"},
    },
    {
        "name": "case7",
        "ticket": {"key": "SSSB-8", "status": "In Progress", "team": "Boreas"},
        "activity": _act(
            "SSSB-8",
            prs=[PR(number=21, state="open", merged=False, title="SSSB-8",
                    url="u", updated_at="2026-06-24T00:00:00Z")],
        ),
        "as_of": AS_OF,
        "is_watermelon": False,
        "actual": "green",
        "required_evidence": set(),
    },
]


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


def build_cases() -> list[Case]:
    cases: list[Case] = []
    for rec in CASES:
        inputs = {"ticket": rec["ticket"], "activity": rec["activity"]}
        if "as_of" in rec:
            inputs["as_of"] = rec["as_of"]
        cases.append(
            Case(
                name=rec["name"],
                inputs=inputs,
                assertions=[
                    _classification(rec["is_watermelon"], rec["actual"]),
                    _evidence(rec["required_evidence"]),
                ],
            )
        )
    return cases


def null_reconciler(inputs: dict[str, Any]) -> Verdict:
    """Placeholder until reconcile() exists. Abstains, so the suite is RED."""
    return Verdict(
        team=inputs["ticket"].get("team", ""),
        reported_status="unknown",
        actual_status="unknown",
        is_watermelon=False,
        evidence=[],
        explanation="no reconciler implemented yet",
    )


def run_cross_tool_eval(reconciler: Reconciler | None = None) -> SuiteReport:
    return run_suite(build_cases(), reconciler or null_reconciler)
