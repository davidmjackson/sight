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
from sprintsight.ingest.embedding import make_embedder
from sprintsight.report.audience import PROFILES
from sprintsight.report.llm_writer import make_llm_writer
from sprintsight.report.render import heading_for
from sprintsight.report.writer import ReportWriter, compose

TEAMS: list[str] = ["Atlas", "Boreas", "Cygnus", "Draco", "Echo"]
_SPRINTS = [14, 15]
CURRENT_SPRINT = _SPRINTS[-1]

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


# --- DB-backed evidence read (real-wiring slice 4), fail-safe and off by default ---
_DB_FLAG = "SPRINTSIGHT_WEB_DB"


def _db_enabled() -> bool:
    """True only when the DB read is deliberately on AND a DATABASE_URL is set (fail-safe)."""
    return os.environ.get(_DB_FLAG) == "on" and bool(os.environ.get("DATABASE_URL"))


def _make_retriever():
    """Build the production retriever. Seam: tests inject a fake; psycopg stays lazy until here."""
    from sprintsight.retrieval.postgres import PostgresRetriever

    return PostgresRetriever(os.environ["DATABASE_URL"])


def db_knowledge_for(team: str, k: int = 5) -> list["KnowledgeItem"]:
    """Cited evidence for one team, read from the live DB and team-scoped (slice-3 team_id).

    Off by default: returns [] unless the gate is open. Fail-safe: any error (no DB, bad creds,
    query failure) is logged and yields [], so the page never 500s on a DB problem.
    """
    if not _db_enabled():
        return []
    query = f"{team} sprint {CURRENT_SPRINT} status risks blockers burndown"
    retriever = None
    try:
        retriever = _make_retriever()
        chunks = retriever.search(query, make_embedder(), k=k, team=team)
        return [_knowledge_item(c) for c in chunks]
    except Exception:
        logging.exception("DB knowledge read failed for team %s", team)
        return []
    finally:
        if retriever is not None:
            retriever.close()


# --- DB-backed verdict/report source (verdict-off-DB slice), fail-safe and off by default ---
_VERDICT_DB_FLAG = "SPRINTSIGHT_VERDICT_DB"


def _verdict_db_enabled() -> bool:
    """True only when the verdict-DB switch is deliberately on AND a DATABASE_URL is set."""
    return os.environ.get(_VERDICT_DB_FLAG) == "on" and bool(os.environ.get("DATABASE_URL"))


def _make_artifact_source():
    """Build the production artifact source. Seam: tests inject a fake; psycopg stays lazy."""
    from sprintsight.retrieval.db_corpus import PostgresArtifactSource

    return PostgresArtifactSource(os.environ["DATABASE_URL"])


def _artifacts_for(team: str) -> dict[str, Artifact]:
    """Team artifacts for the verdict and report. DB when the verdict-DB gate is open, else the
    corpus. Fail-safe: any DB error, or an empty (un-backfilled) result, falls back to the corpus
    so the app never blanks out or 500s on a DB problem."""
    if not _verdict_db_enabled():
        return artifacts_for(team, _SPRINTS)
    source = None
    try:
        source = _make_artifact_source()
        arts = source.artifacts_for(team, _SPRINTS)
        return arts if arts else artifacts_for(team, _SPRINTS)
    except Exception:
        logging.exception("DB artifact source failed for team %s; using corpus", team)
        return artifacts_for(team, _SPRINTS)
    finally:
        if source is not None:
            source.close()


def _knowledge_item(chunk) -> "KnowledgeItem":
    snippet = chunk.text.strip().splitlines()[0][:200] if chunk.text.strip() else ""
    label = _SOURCE_LABELS.get(chunk.source_type, chunk.source_type.title() or "Artifact")
    return KnowledgeItem(
        source_type=chunk.source_type,
        source_ref=chunk.source_ref,
        title=label,
        snippet=snippet,
        score=round(float(chunk.score), 2),
    )


_report_cache: dict[tuple[str, str], tuple[list["ReportSection"], list["EvidenceItem"], bool]] = {}


def clear_report_cache() -> None:
    """Drop all memoized reports. Used between tests; production clears on restart."""
    _report_cache.clear()


@dataclass(frozen=True)
class PortfolioSummary:
    teams_tracked: int
    watermelons: int
    insufficient: int
    sprint: int


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
class KnowledgeItem:
    """One cited chunk read from the live DB for the team drill-in (slice 4)."""

    source_type: str
    source_ref: str
    title: str
    snippet: str
    score: float


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
    db_knowledge: list[KnowledgeItem] = field(default_factory=list)


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


def summarize(rows: list[TeamRow]) -> PortfolioSummary:
    """Fold the portfolio rows into headline counts for the summary band.

    Pure function of rows already in hand: no I/O, so it cannot disagree with the
    table rendered beneath it.
    """
    return PortfolioSummary(
        teams_tracked=len(rows),
        watermelons=sum(1 for r in rows if r.is_watermelon),
        insufficient=sum(1 for r in rows if not r.has_verdict),
        sprint=CURRENT_SPRINT,
    )


def team_detail(team_id: str, audience: str = DEFAULT_AUDIENCE) -> TeamDetail | None:
    team = _resolve_team(team_id)
    if team is None:
        return None
    audience = normalize_audience(audience)
    knowledge = db_knowledge_for(team)
    verdict = _verdict_or_none(team)
    if verdict is None:
        return _insufficient_detail(team, audience, knowledge)
    arts = _artifacts_for(team)
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
        db_knowledge=knowledge,
    )


def _verdict_or_none(team: str) -> Verdict | None:
    """Run the detector, or return None when the team has too little data to judge."""
    arts = _artifacts_for(team)
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


def _insufficient_detail(
    team: str,
    audience: str = DEFAULT_AUDIENCE,
    knowledge: list[KnowledgeItem] | None = None,
) -> TeamDetail:
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
        db_knowledge=knowledge or [],
    )
