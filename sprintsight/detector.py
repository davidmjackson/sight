"""Baseline watermelon detector (SS-2.7).

Consumes a team's artifacts and emits the SS-1.4 `Verdict`: reported vs actual status,
the watermelon flag, the evidence that proves it, and a short explanation. Recommend-only —
it never writes to a RAID log (moat principle B3); it surfaces findings for a human.

The reasoning, deterministic and explainable:
  * reported_status: parsed from the team's Sprint-15 status report.
  * actual_status: from the burn ratio (completed/committed) in bands, corroborated by
    velocity decline, carry-over growth, and flat burndown across both sprints. A late bug
    spike escalates ONLY if there is no triage artifact showing it is under control (the
    Draco near-miss guard).
  * is_watermelon: reported is healthier than actual (rank(reported) < rank(actual)).
  * evidence: the status / burndown / RAID for the judged sprint, plus any hidden
    dependency raised in chat-but-not-RAID (B1/B3) and any bug-spike + triage pair.

Signal thresholds follow the moat spec (B2) and are transparent, not hard gates.
"""

import re
from dataclasses import dataclass
from typing import Any

from sprintsight.evals.fixtures import Artifact
from sprintsight.evals.watermelon import Verdict

_RANK = {"green": 0, "amber": 1, "red": 2}
_BY_RANK = {v: k for k, v in _RANK.items()}

# Transparent reference thresholds (B2; tunable, not hard gates).
GREEN_BURN = 0.9
AMBER_BURN = 0.6
VELOCITY_DECLINE = 0.25
CARRYOVER_GROWTH = 1.5


@dataclass(frozen=True)
class Metrics:
    committed: float
    completed: float
    carry_over: float
    velocity: float


def _num(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def parse_metrics(body: str) -> Metrics:
    """Tolerant extraction of the sprint metrics from a burndown artifact (format varies)."""
    return Metrics(
        committed=_num(r"committed[^\d]*?(\d+)", body) or 0.0,
        completed=_num(r"completed[^\d]*?(\d+)", body) or 0.0,
        carry_over=_num(r"carry-?over[^\d]*?(\d+)", body) or 0.0,
        velocity=_num(r"velocity[^\d]*?(\d+)", body) or 0.0,
    )


def parse_reported_status(body: str) -> str:
    """Read the reported RAG from a status report's 'Overall status' line (emoji-tolerant)."""
    m = re.search(r"overall status[^\n]*?(green|amber|red)", body, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    found = [(body.lower().find(tok), tok) for tok in _RANK if tok in body.lower()]
    return min(found)[1] if found else "green"


def _band(burn_ratio: float) -> str:
    if burn_ratio >= GREEN_BURN:
        return "green"
    if burn_ratio >= AMBER_BURN:
        return "amber"
    return "red"


def _escalate(status: str) -> str:
    return _BY_RANK[min(_RANK[status] + 1, 2)]


def _find_in_sprint(arts: dict[str, Artifact], prefix: str, sprint: int) -> str | None:
    for aid, a in arts.items():
        if aid.startswith(prefix) and a.sprint == sprint:
            return aid
    return None


def _find_hidden_dependency(arts: dict[str, Artifact], raid_body: str) -> str | None:
    """A dependency/blocker raised in chat (Sprint 15) but absent from the RAID (B1/B3)."""
    raid = raid_body.lower()
    risk = re.compile(r"isn't ready|not ready|slipp|bite us|won't hold|blocked|building on sand")
    depend = re.compile(r"api|dependency|endpoint|service")
    for aid, a in arts.items():
        if a.source_type != "slack" or a.sprint != 15:
            continue
        body = a.body.lower()
        if not (risk.search(body) and depend.search(body)):
            continue
        salient = re.findall(r"[a-z]+-\d+", body)
        if "auth api" in body:
            salient.append("auth api")
        # Hidden if its salient subject is not echoed in the RAID.
        if not salient or not any(s in raid for s in salient):
            return aid
    return None


def detect(inputs: dict[str, Any]) -> Verdict:
    """The SS-1.4 detector contract. `inputs` = {"team", "artifacts"}."""
    team: str = inputs["team"]
    arts: dict[str, Artifact] = inputs["artifacts"]
    t = team.lower()

    status_id = f"status-{t}-s15"
    burndown_s15 = f"burndown-{t}-s15"
    burndown_s14 = f"burndown-{t}-s14"
    raid_id = f"raid-{t}-s15"

    m15 = parse_metrics(arts[burndown_s15].body)
    m14 = parse_metrics(arts[burndown_s14].body) if burndown_s14 in arts else None
    reported = parse_reported_status(arts[status_id].body)

    burn15 = m15.completed / m15.committed if m15.committed else 1.0
    actual = _band(burn15)

    signals: list[str] = [f"burn ratio {burn15:.2f} (S15) -> {actual}"]
    if m14 and m14.velocity:
        decline = (m14.velocity - m15.velocity) / m14.velocity
        if decline >= VELOCITY_DECLINE:
            signals.append(
                f"velocity decline {decline:.0%} "
                f"({m14.velocity:.0f}->{m15.velocity:.0f})"
            )
    if m14 and m14.carry_over and (m15.carry_over / m14.carry_over) >= CARRYOVER_GROWTH:
        signals.append(f"carry-over growth {m14.carry_over:.0f}->{m15.carry_over:.0f}")

    # Bug-spike near-miss guard: escalate only if not shown under control by a triage artifact.
    bugspike_id = _find_in_sprint(arts, "bugspike-", 15)
    triage_id = _find_in_sprint(arts, "triage-", 15)
    if bugspike_id and not triage_id:
        actual = _escalate(actual)
        signals.append("bug spike with no triage -> escalated")
    elif bugspike_id and triage_id:
        signals.append("bug spike present but triaged (under control) -> not escalated")

    raid_body = arts[raid_id].body if raid_id in arts else ""
    hidden_dep = _find_hidden_dependency(arts, raid_body)
    if hidden_dep:
        signals.append("dependency raised in chat but missing from RAID")

    is_watermelon = _RANK[reported] < _RANK[actual]

    evidence = [status_id, burndown_s15, raid_id]
    if hidden_dep:
        evidence.append(hidden_dep)
    if bugspike_id:
        evidence.append(bugspike_id)
    if triage_id:
        evidence.append(triage_id)
    evidence = [e for e in evidence if e in arts]

    verb = "looks healthier than reality" if is_watermelon else "matches the reported status"
    explanation = (
        f"{team} reported {reported}; computed actual {actual} ({verb}). "
        + "; ".join(signals)
        + "."
    )

    return Verdict(
        team=team,
        reported_status=reported,
        actual_status=actual,
        is_watermelon=is_watermelon,
        evidence=evidence,
        signals=signals,
        explanation=explanation,
    )
