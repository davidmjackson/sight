"""Stage 6 web data layer (SS-6).

Reads the synthetic corpus through the existing detector path and shapes view-models for
the portfolio grid and the per-team drill-in. Pure Python: no HTTP, no LLM, no database.
The detector sits behind this seam so a future DB-backed detector can replace it without
touching the pages. The portfolio judges as-of Sprint 15 with Sprint 14 as context.
"""

import logging
from dataclasses import dataclass, field

from sprintsight.evals.fixtures import Artifact, artifacts_for
from sprintsight.evals.watermelon import Verdict
from sprintsight.graph.builder import graph_detector
from sprintsight.report.render import heading_for
from sprintsight.report.writer import ReportWriter, compose

TEAMS: list[str] = ["Atlas", "Boreas", "Cygnus", "Draco", "Echo"]
_SPRINTS = [14, 15]

_SOURCE_LABELS = {
    "status": "Status report",
    "burndown": "Burndown",
    "raid": "RAID log",
    "slack": "Chat message",
    "chat": "Chat message",
    "jira": "Jira ticket",
    "triage": "Triage note",
    "bugspike": "Bug spike",
}

_detector = graph_detector()

DEFAULT_AUDIENCE = "programme"
VALID_AUDIENCES = ("exec", "programme", "team")

_writer: ReportWriter = compose  # seam; LLM writer can be injected here later


def normalize_audience(value: str) -> str:
    """Coerce any audience value to a valid one; unknown falls back to the default."""
    return value if value in VALID_AUDIENCES else DEFAULT_AUDIENCE


@dataclass(frozen=True)
class ReportSection:
    heading: str
    body: str


@dataclass(frozen=True)
class EvidenceItem:
    artifact_id: str
    source_type: str
    sprint: int
    title: str
    snippet: str


@dataclass(frozen=True)
class TeamRow:
    team: str
    reported_status: str
    actual_status: str
    is_watermelon: bool
    headline: str
    has_verdict: bool


@dataclass(frozen=True)
class TeamDetail:
    team: str
    reported_status: str
    actual_status: str
    is_watermelon: bool
    headline: str
    has_verdict: bool
    signals: list[str] = field(default_factory=list)
    explanation: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)
    audience: str = DEFAULT_AUDIENCE
    report_sections: list[ReportSection] = field(default_factory=list)
    report_sources: list[EvidenceItem] = field(default_factory=list)
    report_insufficient: bool = False


def portfolio() -> list[TeamRow]:
    rows: list[TeamRow] = []
    for team in TEAMS:
        verdict = _verdict_or_none(team)
        if verdict is None:
            rows.append(_insufficient_row(team))
            continue
        rows.append(
            TeamRow(
                team=team,
                reported_status=verdict.reported_status,
                actual_status=verdict.actual_status,
                is_watermelon=verdict.is_watermelon,
                headline=_headline(verdict),
                has_verdict=True,
            )
        )
    return rows


def team_detail(team_id: str, audience: str = DEFAULT_AUDIENCE) -> TeamDetail | None:
    team = _resolve_team(team_id)
    if team is None:
        return None
    audience = normalize_audience(audience)
    verdict = _verdict_or_none(team)
    if verdict is None:
        return _insufficient_detail(team, audience)
    arts = artifacts_for(team, _SPRINTS)
    sections, sources, insufficient = _report_for(team, audience, arts)
    return TeamDetail(
        team=team,
        reported_status=verdict.reported_status,
        actual_status=verdict.actual_status,
        is_watermelon=verdict.is_watermelon,
        headline=_headline(verdict),
        has_verdict=True,
        signals=list(verdict.signals),
        explanation=verdict.explanation,
        evidence=[_evidence_item(aid, arts) for aid in verdict.evidence],
        audience=audience,
        report_sections=sections,
        report_sources=sources,
        report_insufficient=insufficient,
    )


def _verdict_or_none(team: str) -> Verdict | None:
    """Run the detector, or return None when the team has too little data to judge."""
    arts = artifacts_for(team, _SPRINTS)
    if not _has_minimum(team, arts):
        return None
    try:
        return _detector({"team": team, "artifacts": arts})
    except Exception:
        logging.exception("detector failed for team %s", team)
        return None


def _has_minimum(team: str, arts: dict[str, Artifact]) -> bool:
    t = team.lower()
    return f"status-{t}-s15" in arts and f"burndown-{t}-s15" in arts


def _resolve_team(team_id: str) -> str | None:
    for team in TEAMS:
        if team.lower() == team_id.lower():
            return team
    return None


def _headline(verdict: Verdict) -> str:
    base = f"Reported {verdict.reported_status}, computed {verdict.actual_status}"
    if verdict.is_watermelon:
        return f"{base} (looks healthier than it is)."
    return f"{base} (consistent)."


def _report_sources(report, arts: dict[str, Artifact]) -> list[EvidenceItem]:
    """Unique cited artifacts behind the report's claims, in first-cited order."""
    seen: list[str] = []
    out: list[EvidenceItem] = []
    for claim in report.claims:
        for cid in claim.citations:
            if cid not in seen:
                seen.append(cid)
                out.append(_evidence_item(cid, arts))
    return out


def _report_for(
    team: str, audience: str, arts: dict[str, Artifact]
) -> tuple[list[ReportSection], list[EvidenceItem], bool]:
    """Run the writer seam and shape its report for display."""
    report = _writer({"team": team, "audience": audience, "artifacts": arts})
    if report.insufficient_evidence:
        return [], [], True
    sections = [ReportSection(heading_for(k), v) for k, v in report.sections.items()]
    return sections, _report_sources(report, arts), False


def _evidence_item(artifact_id: str, arts: dict[str, Artifact]) -> EvidenceItem:
    art = arts.get(artifact_id)
    if art is None:
        return EvidenceItem(artifact_id, "unknown", 0, artifact_id, "")
    label = _SOURCE_LABELS.get(art.source_type, art.source_type.title() or "Artifact")
    snippet = art.body.strip().splitlines()[0][:200] if art.body.strip() else ""
    return EvidenceItem(
        artifact_id=art.artifact_id,
        source_type=art.source_type,
        sprint=art.sprint,
        title=f"{label} (Sprint {art.sprint})",
        snippet=snippet,
    )


def _insufficient_row(team: str) -> TeamRow:
    return TeamRow(
        team=team,
        reported_status="unknown",
        actual_status="unknown",
        is_watermelon=False,
        headline="Insufficient evidence to judge this team.",
        has_verdict=False,
    )


def _insufficient_detail(team: str, audience: str = DEFAULT_AUDIENCE) -> TeamDetail:
    return TeamDetail(
        team=team,
        reported_status="unknown",
        actual_status="unknown",
        is_watermelon=False,
        headline="Insufficient evidence to judge this team.",
        has_verdict=False,
        signals=[],
        explanation="This team has too little Sprint 15 data (no burndown or status) to judge.",
        evidence=[],
        audience=normalize_audience(audience),
        report_sections=[],
        report_sources=[],
        report_insufficient=True,
    )
