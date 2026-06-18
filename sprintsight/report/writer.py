"""The report-writer seam.

`ReportWriter` is any callable `inputs -> Report`. `null_writer` abstains (eval-first RED
signal). The deterministic `compose` lands in Story B; an Anthropic-backed writer is a later
drop-in behind the same callable (open-wiring item, not built here).
"""

from collections.abc import Callable
from typing import Any

from sprintsight.detector import Metrics
from sprintsight.evals.fixtures import Artifact
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
