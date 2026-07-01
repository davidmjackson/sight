"""Cross-team dependency-slip reconciler (moat Behaviour 1 + 3).

Pure and recommend-only. Given a dependency a consumer team names in its own chat
(e.g. Atlas naming Draco's DRACO-412), this reads the PROVIDER team's own artifacts,
confirms the item is genuinely slipping, and reports a CrossTeamRisk citing both sides.
It also flags whether the consumer logged the dependency in its RAID (Behaviour 3's
"recommend logging it"). It never writes anything.

Scope guardrail (moat spec, LOCKED): only dependencies explicitly named in an artifact
are reconciled. No general dependency-graph engine, no inferred links.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from sprintsight.evals.fixtures import Artifact

# A Jira-style reference like DRACO-412 (team prefix + number).
_REF = re.compile(r"[A-Za-z]{2,}-\d+")
# Risk + dependency vocabulary, consistent with detector._find_hidden_dependency.
_RISK = re.compile(
    r"isn't ready|not ready|slipp|bite us|won't hold|blocked|building on sand|late", re.I
)
_DEP = re.compile(r"api|dependency|endpoint|service", re.I)
# The provider item is slipping if it uses slip language and is not marked done/closed.
_SLIP = re.compile(r"slipp|delayed|pushed to sprint|carried over|now targeted", re.I)
_DONE = re.compile(r"status[^\n|]*[|:]\s*(done|closed|shipped|released)", re.I)
_SLIP_TO = re.compile(r"slipp\w*\s+to\s+(sprint\s*\d+)", re.I)
_SUMMARY = re.compile(r"\|\s*Summary\s*\|\s*([^|]+?)\s*\|", re.I)


@dataclass(frozen=True)
class CrossTeamRisk:
    consumer_team: str
    provider_team: str
    dependency_ref: str
    dependency_label: str
    slip_detail: str
    logged_in_raid: bool
    consumer_citation: str
    provider_citations: list[str] = field(default_factory=list)
    headline: str = ""


def _provider_from_ref(ref: str) -> str:
    return ref.split("-")[0].title()


def _consumer_raid_body(consumer_arts: dict[str, Artifact]) -> str:
    for a in consumer_arts.values():
        if a.source_type == "raid" and a.sprint == 15:
            return a.body.lower()
    return ""


def _find_provider_ticket(ref: str, arts: dict[str, Artifact]) -> Artifact | None:
    for a in arts.values():
        if str(a.meta.get("source_ref", "")).upper() == ref.upper():
            return a
    for a in arts.values():
        if ref.lower() in a.artifact_id.lower():
            return a
    return None


def _summary(body: str, fallback: str) -> str:
    m = _SUMMARY.search(body)
    return m.group(1).strip() if m else fallback


def _slip_detail(body: str) -> str:
    m = _SLIP_TO.search(body)
    return f"slipped to {m.group(1)}" if m else "flagged as slipping on the provider side"


def _clean_label(label: str, provider_team: str) -> str:
    words = label.split()
    if words and words[0].lower() == provider_team.lower():
        return " ".join(words[1:])
    return label


def reconcile_cross_team(
    consumer_team: str,
    consumer_arts: dict[str, Artifact],
    provider_arts_for: Callable[[str], dict[str, Artifact]],
) -> CrossTeamRisk | None:
    raid_body = _consumer_raid_body(consumer_arts)
    for a in consumer_arts.values():
        if a.source_type != "slack" or a.sprint != 15:
            continue
        if not (_RISK.search(a.body) and _DEP.search(a.body)):
            continue
        for ref in _REF.findall(a.body):
            provider_team = _provider_from_ref(ref)
            if provider_team.lower() == consumer_team.lower():
                continue  # a self-reference is not cross-team
            provider_arts = provider_arts_for(provider_team)
            ticket = _find_provider_ticket(ref, provider_arts)
            if ticket is None:
                continue  # provider/ticket not tracked -> cannot reconcile
            if not _SLIP.search(ticket.body) or _DONE.search(ticket.body):
                continue  # named but on track -> do not cry wolf
            label = _summary(ticket.body, ref)
            logged = ref.lower() in raid_body or label.lower() in raid_body
            slip = _slip_detail(ticket.body)
            others = [
                x.artifact_id
                for x in provider_arts.values()
                if x.artifact_id != ticket.artifact_id
                and ref.lower() in x.body.lower()
                and x.source_type in {"raid", "status", "confluence"}
            ]
            clean = _clean_label(label, provider_team)
            headline = (
                f"{consumer_team} is blocked by {provider_team}'s {clean} "
                f"({ref}), which {slip}."
            )
            return CrossTeamRisk(
                consumer_team=consumer_team,
                provider_team=provider_team,
                dependency_ref=ref,
                dependency_label=label,
                slip_detail=slip,
                logged_in_raid=logged,
                consumer_citation=a.artifact_id,
                provider_citations=[ticket.artifact_id] + others,
                headline=headline,
            )
    return None
