"""The report-writer seam.

`ReportWriter` is any callable `inputs -> Report`. `null_writer` abstains (eval-first RED
signal). The deterministic `compose` lands in Story B; an Anthropic-backed writer is a later
drop-in behind the same callable (open-wiring item, not built here).
"""

import re
from collections.abc import Callable
from typing import Any

from sprintsight.detector import Metrics, parse_metrics, parse_reported_status
from sprintsight.evals.fixtures import Artifact
from sprintsight.report.audience import PROFILES
from sprintsight.report.contract import Claim, Report

ReportWriter = Callable[[dict[str, Any]], Report]


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


def compose(inputs: dict[str, Any]) -> Report:
    """Deterministic, audience-tuned, fully-cited report writer (the SS-1.5 subject)."""
    team: str = inputs["team"]
    audience: str = inputs["audience"]
    arts: dict[str, Artifact] = inputs["artifacts"]
    profile = PROFILES[audience]
    t = team.lower()
    burndown_id = f"burndown-{t}-s15"
    status_id = f"status-{t}-s15"
    raid_id = f"raid-{t}-s15"

    # Thin-data guard (fabrication gate): no burndown -> nothing to substantiate.
    if burndown_id not in arts:
        return Report(team=team, audience=audience, insufficient_evidence=True)

    metrics = parse_metrics(arts[burndown_id].body)
    rag = parse_reported_status(arts[status_id].body) if status_id in arts else "green"
    rag_cite = status_id if status_id in arts else burndown_id
    risks = _risk_lines(arts, raid_id)
    deps = _dependency_lines(arts, raid_id)

    claims = [_rag_claim(rag, rag_cite)]
    sections: dict[str, str] = {}

    if profile.name == "exec":
        sections["overall_rag"] = f"Overall delivery status is {rag}."
        top = risks[:3]
        sections["top_risks"] = " ".join(top) if top else "No material risks reported."
        sections["ask"] = "Decision needed: none this period."
        claims += [Claim(r, [raid_id]) for r in top]
    elif profile.name == "programme":
        claims += _metric_claims(metrics, burndown_id)
        sections["overall_rag"] = f"Delivery status {rag}."
        sections["risks"] = " ".join(risks) if risks else "No risks logged."
        sections["dependencies"] = " ".join(deps) if deps else "No external dependencies logged."
        sections["milestones"] = _looking_ahead(arts, status_id)
        claims += [Claim(r, [raid_id]) for r in risks]
    else:  # team — most granular, no caps, all detail
        claims += _metric_claims(metrics, burndown_id)
        sections["sprint_metrics"] = (
            f"Committed {int(metrics.committed)} points, "
            f"completed {int(metrics.completed)} points, "
            f"velocity {int(metrics.velocity)}, "
            f"{int(metrics.carry_over)} stories carried over."
        )
        sections["ticket_progress"] = (
            "Stories progressed across the sprint; carry-over items remain in flight."
        )
        sections["blockers"] = " ".join(risks) if risks else "No blockers reported."
        claims += [Claim(r, [raid_id]) for r in risks]

    return Report(team=team, audience=audience, sections=sections, claims=claims)
