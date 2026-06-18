"""The SS-1.5 status-report output contract (report-quality-eval.md §2).

Structured so claims and their citations are machine-extractable by the eval.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Claim:
    """One assertion in a report plus the artifact_ids that support it."""

    text: str
    citations: list[str]


@dataclass
class Report:
    """An audience-tuned status report. `sections` keys vary by audience profile."""

    team: str
    audience: str
    sections: dict[str, str] = field(default_factory=dict)
    claims: list[Claim] = field(default_factory=list)
    insufficient_evidence: bool = False
