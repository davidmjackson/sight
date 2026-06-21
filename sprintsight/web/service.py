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


def team_detail(team_id: str) -> TeamDetail | None:
    team = _resolve_team(team_id)
    if team is None:
        return None
    verdict = _verdict_or_none(team)
    if verdict is None:
        return _insufficient_detail(team)
    arts = artifacts_for(team, _SPRINTS)
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


def _insufficient_detail(team: str) -> TeamDetail:
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
    )
