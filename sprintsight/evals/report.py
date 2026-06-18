"""Status-report quality eval (SS-1.5).

Implements docs/evals/report-quality-eval.md on the generic harness. Cases are built from
the SS-2.1 corpus fixtures; grounding (assertion C) is checked against the canonical metrics
in data/ground-truth/labels.yaml, independently of how the writer parsed them.

Subject under test: a `ReportWriter` (inputs -> Report). `null_writer` lands RED; the
deterministic `compose` (Story B/C) turns it GREEN.
"""

import re
from collections.abc import Callable
from typing import Any

from sprintsight.evals.fixtures import artifacts_for, load_ground_truth
from sprintsight.evals.harness import Assertion, Case, CaseResult, SuiteReport, run_suite
from sprintsight.report.audience import MECHANICS_TERMS, PROFILES, TICKET_ID, AudienceProfile
from sprintsight.report.contract import Report
from sprintsight.report.writer import ReportWriter, null_writer

JUDGED_SPRINT = 15
Check = Callable[[Report], Assertion]

# (regex over claim text, ground-truth metric key) for numeric grounding (assertion C).
_GROUNDERS = [
    (re.compile(r"committed\s+(\d+)\s+points", re.I), "committed_points"),
    (re.compile(r"completed\s+(\d+)\s+points", re.I), "completed_points"),
    (re.compile(r"carried over\s+(\d+)\s+stor", re.I), "carry_over_stories"),
    (re.compile(r"velocity\s+(\d+)", re.I), "velocity"),
]
_RAG = re.compile(r"overall status[:\s]+(green|amber|red)", re.I)


def _render(rep: Report) -> str:
    return " ".join(list(rep.sections.values()) + [c.text for c in rep.claims])


def _gt_record(team: str, sprint: int = JUDGED_SPRINT) -> dict[str, Any]:
    return next(
        r for r in load_ground_truth()["records"]
        if r["team"] == team and r["sprint"] == sprint
    )


def _coverage() -> Check:  # A
    def check(rep: Report) -> Assertion:
        uncited = [c.text for c in rep.claims if not c.citations]
        return Assertion("citation_coverage", not uncited,
                         f"uncited={uncited}" if uncited else "all claims cited")
    return check


def _validity(valid_ids: set[str]) -> Check:  # B
    def check(rep: Report) -> Assertion:
        bad = [cid for c in rep.claims for cid in c.citations if cid not in valid_ids]
        return Assertion("citation_validity", not bad,
                         f"invalid={bad}" if bad else "all citations valid")
    return check


def _grounding(metrics: dict[str, Any], reported_status: str) -> Check:  # C
    def check(rep: Report) -> Assertion:
        for c in rep.claims:
            for rx, key in _GROUNDERS:
                m = rx.search(c.text)
                if m and int(m.group(1)) != metrics[key]:
                    return Assertion("grounding", False,
                                     f"{key}={m.group(1)} != truth {metrics[key]}")
            rag = _RAG.search(c.text)
            if rag and rag.group(1).lower() != reported_status:
                return Assertion("grounding", False,
                                 f"RAG={rag.group(1).lower()} != reported {reported_status}")
        return Assertion("grounding", True, "numeric/status claims match ground truth")
    return check


def _required_sections(profile: AudienceProfile) -> Check:  # E
    def check(rep: Report) -> Assertion:
        missing = set(profile.required_sections) - set(rep.sections)
        return Assertion("required_sections", not missing,
                         f"missing={sorted(missing)}" if missing else "all sections present")
    return check


def _audience_fit(profile: AudienceProfile) -> Check:  # D
    def check(rep: Report) -> Assertion:
        text = _render(rep)
        words = len(text.split())
        if profile.max_words and words > profile.max_words:
            return Assertion("audience_fit", False, f"{words} words > cap {profile.max_words}")
        if profile.forbid_ticket_ids and re.search(TICKET_ID, text):
            return Assertion("audience_fit", False, "contains ticket id(s)")
        if profile.forbid_mechanics and any(t in text.lower() for t in MECHANICS_TERMS):
            return Assertion("audience_fit", False, "contains sprint mechanics")
        return Assertion("audience_fit", True, f"{words} words, profile respected")
    return check


def _no_fabrication(valid_ids: set[str]) -> Check:  # F
    def check(rep: Report) -> Assertion:
        if not rep.insufficient_evidence:
            return Assertion("no_fabrication", False, "did not flag insufficient evidence")
        bad = [cid for c in rep.claims for cid in c.citations if cid not in valid_ids]
        numeric = [c.text for c in rep.claims if re.search(r"\d", c.text)]
        ok = not bad and not numeric
        return Assertion("no_fabrication", ok,
                         f"invented={bad} numeric={numeric}" if not ok else "no fabrication")
    return check


def build_cases() -> list[Case]:
    """Cases 1-3 of the spec; the audience-triple (Case 4) is appended in run_report_eval."""
    boreas = _gt_record("Boreas")
    atlas = _gt_record("Atlas")
    boreas_ids = set(artifacts_for("Boreas", [JUDGED_SPRINT]))
    atlas_ids = set(artifacts_for("Atlas", [JUDGED_SPRINT]))
    echo_ids = set(artifacts_for("Echo", [JUDGED_SPRINT]))
    return [
        Case(
            "boreas-exec",
            {"team": "Boreas", "audience": "exec",
             "artifacts": artifacts_for("Boreas", [JUDGED_SPRINT])},
            [_coverage(), _validity(boreas_ids),
             _grounding(boreas["metrics"], boreas["reported_status"]),
             _required_sections(PROFILES["exec"]), _audience_fit(PROFILES["exec"])],
        ),
        Case(
            "atlas-programme",
            {"team": "Atlas", "audience": "programme",
             "artifacts": artifacts_for("Atlas", [JUDGED_SPRINT])},
            [_coverage(), _validity(atlas_ids),
             _grounding(atlas["metrics"], atlas["reported_status"]),
             _required_sections(PROFILES["programme"]), _audience_fit(PROFILES["programme"])],
        ),
        Case(
            "echo-thin",
            {"team": "Echo", "audience": "exec",
             "artifacts": artifacts_for("Echo", [JUDGED_SPRINT])},
            [_no_fabrication(echo_ids)],
        ),
    ]


def _audience_triple(writer: ReportWriter) -> CaseResult:
    """Case 4: same Boreas s15 across exec/programme/team must differentiate."""
    arts = artifacts_for("Boreas", [JUDGED_SPRINT])
    rendered = {
        aud: _render(writer({"team": "Boreas", "audience": aud, "artifacts": arts}))
        for aud in ("exec", "programme", "team")
    }
    we, wp, wt = (len(rendered[a].split()) for a in ("exec", "programme", "team"))
    distinct = len(set(rendered.values())) == 3
    exec_clean = not any(t in rendered["exec"].lower() for t in MECHANICS_TERMS)
    team_granular = "points" in rendered["team"].lower()
    ok = distinct and we < wp and we < wt and exec_clean and team_granular
    detail = (f"words exec={we} prog={wp} team={wt}; distinct={distinct} "
              f"exec_clean={exec_clean} team_granular={team_granular}")
    return CaseResult("audience-triple", ok, [Assertion("audience_differentiation", ok, detail)])


def run_report_eval(writer: ReportWriter | None = None) -> SuiteReport:
    """Run the report suite; default writer is the abstaining null writer (RED)."""
    writer = writer or null_writer
    report = run_suite(build_cases(), writer)
    report.results.append(_audience_triple(writer))
    return report
