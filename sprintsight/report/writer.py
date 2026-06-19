"""The report-writer seam.

`ReportWriter` is any callable `inputs -> Report`. `null_writer` abstains (eval-first RED
signal). The deterministic `compose` lands in Story B; an Anthropic-backed writer is a later
drop-in behind the same callable (open-wiring item, not built here).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sprintsight.detector import Metrics, parse_metrics, parse_reported_status
from sprintsight.evals.fixtures import Artifact
from sprintsight.report.audience import PROFILES, AudienceProfile
from sprintsight.report.contract import Claim, Report

ReportWriter = Callable[[dict[str, Any]], Report]


@dataclass
class Facts:
    """Deterministically grounded inputs for one report (single-sourced for compose + LLM)."""

    team: str
    audience: str
    profile: AudienceProfile
    burndown_id: str
    status_id: str
    raid_id: str
    metrics: Metrics | None
    rag: str
    rag_cite: str
    risks: list[str]
    deps: list[str]
    looking_ahead: str
    claims: list[Claim]
    insufficient: bool


def null_writer(inputs: dict[str, Any]) -> Report:
    """Abstains: empty report, so every case fails its assertions (RED by design)."""
    return Report(team=inputs["team"], audience=inputs["audience"])


def _metric_claims(m: Metrics, burndown_id: str) -> list[Claim]:
    return [
        Claim(f"Committed {int(m.committed)} points.", [burndown_id]),
        Claim(f"Completed {int(m.completed)} points.", [burndown_id]),
        Claim(f"Carried over {int(m.carry_over)} stories.", [burndown_id]),
        Claim(f"Velocity {int(m.velocity)}.", [burndown_id]),
    ]


def _rag_claim(rag: str, cite: str) -> Claim:
    return Claim(f"Overall status: {rag}.", [cite])


def _table_descriptions(body: str, heading: str) -> list[str]:
    """Second-column cells of the markdown table under `## <heading>` (skips id + header)."""
    out: list[str] = []
    in_section = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower() == f"## {heading.lower()}"
            continue
        if in_section and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            col = cells[1].lower()
            if len(cells) < 2 or set(cells[1]) <= {"-"} or col in {"risk", "dependency"}:
                continue  # separator or header row
            out.append(cells[1])
    return out


def _risk_lines(arts: dict[str, Artifact], raid_id: str) -> list[str]:
    if raid_id not in arts:
        return []
    return _table_descriptions(arts[raid_id].body, "Risks")


def _dependency_lines(arts: dict[str, Artifact], raid_id: str) -> list[str]:
    if raid_id not in arts:
        return []
    return _table_descriptions(arts[raid_id].body, "Dependencies")


def _looking_ahead(arts: dict[str, Artifact], status_id: str) -> str:
    """A milestones blurb pulled from the status report's forward-looking prose (no ids)."""
    if status_id not in arts:
        return "Sprint 16 planning underway."
    for line in arts[status_id].body.splitlines():
        low = line.lower()
        if "sprint 16" in low and not re.search(r"[A-Z][A-Z0-9]+-\d+", line):
            return line.strip()
    return "Sprint 16 planning underway."


def _as_list(items: list[str]) -> str:
    """Render RAID-derived items as a clean markdown bullet list, one per line.

    Replaces the old ' '.join(...) that ran separate risks together into one blob.
    Each item gets a single trailing period (existing trailing periods/spaces are
    normalised first).
    """
    return "\n".join(f"- {i.rstrip('. ').strip()}." for i in items)


def _grounded_facts(inputs: dict[str, Any]) -> Facts:
    team: str = inputs["team"]
    audience: str = inputs["audience"]
    arts: dict[str, Artifact] = inputs["artifacts"]
    profile = PROFILES[audience]
    t = team.lower()
    burndown_id = f"burndown-{t}-s15"
    status_id = f"status-{t}-s15"
    raid_id = f"raid-{t}-s15"

    if burndown_id not in arts:  # thin-data guard (fabrication gate)
        return Facts(
            team,
            audience,
            profile,
            burndown_id,
            status_id,
            raid_id,
            None,
            "",
            "",
            [],
            [],
            "",
            [],
            insufficient=True,
        )

    metrics = parse_metrics(arts[burndown_id].body)
    rag = parse_reported_status(arts[status_id].body) if status_id in arts else "green"
    rag_cite = status_id if status_id in arts else burndown_id
    risks = _risk_lines(arts, raid_id)
    deps = _dependency_lines(arts, raid_id)
    looking_ahead = _looking_ahead(arts, status_id)

    claims = [_rag_claim(rag, rag_cite)]
    if profile.name == "exec":
        claims += [Claim(r, [raid_id]) for r in risks[:3]]
    else:  # programme + team both carry metric claims and all risk claims
        claims += _metric_claims(metrics, burndown_id)
        claims += [Claim(r, [raid_id]) for r in risks]

    return Facts(
        team,
        audience,
        profile,
        burndown_id,
        status_id,
        raid_id,
        metrics,
        rag,
        rag_cite,
        risks,
        deps,
        looking_ahead,
        claims,
        insufficient=False,
    )


def _exec_ask(f: Facts) -> str:
    """Grounded, forward-looking exec ask.

    Keys on whether risks are logged (a report can be reported green yet still carry
    risks). Names only a risk already logged and recommends an owner be confirmed; it
    invents no owner, date, or decision. Human-in-the-loop: this is recommend-only prose.
    """
    risks = f.risks[:3]
    if not risks:
        return "No decision needed this period; delivery on track."
    top = risks[0].rstrip(". ").strip()
    if len(risks) == 1:
        return (
            f"Recommended next step: one risk logged ({top}); "
            "confirm it is owned and tracked before sprint close."
        )
    return (
        f"Recommended next step: {len(risks)} risks logged (see above). "
        f"The most exposed is {top}; confirm it is owned and tracked before sprint close."
    )


def _compose_sections(f: Facts) -> dict[str, str]:
    sections: dict[str, str] = {}
    if f.profile.name == "exec":
        sections["overall_rag"] = f"Overall delivery status is {f.rag}."
        top = f.risks[:3]
        sections["top_risks"] = _as_list(top) if top else "No material risks reported."
        sections["ask"] = _exec_ask(f)
    elif f.profile.name == "programme":
        sections["overall_rag"] = f"Delivery status {f.rag}."
        sections["risks"] = _as_list(f.risks) if f.risks else "No risks logged."
        sections["dependencies"] = (
            _as_list(f.deps) if f.deps else "No external dependencies logged."
        )
        sections["milestones"] = f.looking_ahead
    else:  # team
        m = f.metrics
        sections["sprint_metrics"] = (
            f"Committed {int(m.committed)} points, "
            f"completed {int(m.completed)} points, "
            f"velocity {int(m.velocity)}, "
            f"{int(m.carry_over)} stories carried over."
        )
        sections["ticket_progress"] = (
            "Stories progressed across the sprint; carry-over items remain in flight."
        )
        sections["blockers"] = _as_list(f.risks) if f.risks else "No blockers reported."
    return sections


def compose(inputs: dict[str, Any]) -> Report:
    """Deterministic, audience-tuned, fully-cited report writer (the SS-1.5 subject)."""
    f = _grounded_facts(inputs)
    if f.insufficient:
        return Report(team=f.team, audience=f.audience, insufficient_evidence=True)
    return Report(team=f.team, audience=f.audience, sections=_compose_sections(f), claims=f.claims)
