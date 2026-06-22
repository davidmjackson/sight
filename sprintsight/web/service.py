"""Stage 6 web data layer (SS-6).

Reads the synthetic corpus through the existing detector path and shapes view-models for
the portfolio grid and the per-team drill-in. No HTTP server and no database; the report
writer is offline `compose` by default, with an optional call-time-gated LLM writer (off
unless SPRINTSIGHT_WEB_LLM=on and a real key are present). The detector sits behind this
seam so a future DB-backed detector can replace it without touching the pages. The
portfolio judges as-of Sprint 15 with Sprint 14 as context.
"""

import logging
import os
from dataclasses import dataclass, field

from sprintsight.evals.fixtures import Artifact, artifacts_for
from sprintsight.evals.watermelon import Verdict
from sprintsight.graph.builder import graph_detector
from sprintsight.report.audience import PROFILES
from sprintsight.report.llm_writer import make_llm_writer
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


_LLM_FLAG = "SPRINTSIGHT_WEB_LLM"


def _has_real_key() -> bool:
    """A real Anthropic key has the sk-ant- shape and real length; blank/fake keys do not."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key.startswith("sk-ant-") and len(key) > 50


def _llm_enabled() -> bool:
    """True only when the brain is deliberately on AND a real key is present (fail-safe)."""
    return os.environ.get(_LLM_FLAG) == "on" and _has_real_key()


def _active_writer() -> ReportWriter:
    """The writer this request should use: the LLM writer when the gate is open, else the
    injected/default seam (compose offline)."""
    if _llm_enabled():
        return make_llm_writer()
    return _writer


_report_cache: dict[tuple[str, str], tuple[list["ReportSection"], list["EvidenceItem"], bool]] = {}


def clear_report_cache() -> None:
    """Drop all memoized reports. Used between tests; production clears on restart."""
    _report_cache.clear()


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


def _ordered_section_keys(audience: str, sections: dict[str, str]) -> list[str]:
    """Order sections by the audience profile, not writer insertion order, so a future
    writer that emits sections in a different order still renders in the intended order."""
    order = PROFILES[audience].required_sections
    ordered = [k for k in order if k in sections]
    extra = [k for k in sections if k not in order]
    return ordered + extra


def _report_for(
    team: str, audience: str, arts: dict[str, Artifact]
) -> tuple[list[ReportSection], list[EvidenceItem], bool]:
    """Run the writer seam and shape its report for display, memoized per (team, audience)."""
    cache_key = (team, audience)
    cached = _report_cache.get(cache_key)
    if cached is not None:
        return cached
    report = _active_writer()({"team": team, "audience": audience, "artifacts": arts})
    if report.insufficient_evidence:
        result: tuple[list[ReportSection], list[EvidenceItem], bool] = ([], [], True)
    else:
        sections = [
            ReportSection(heading_for(k), report.sections[k])
            for k in _ordered_section_keys(audience, report.sections)
        ]
        result = (sections, _report_sources(report, arts), False)
    _report_cache[cache_key] = result
    return result


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
