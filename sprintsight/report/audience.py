"""Audience profiles (report-quality-eval.md §4, LOCKED).

Single source of truth for length caps, required section keys, and forbidden detail
markers. Read by both the composer (to shape output) and the eval (to score audience fit).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AudienceProfile:
    name: str
    max_words: int | None  # None = no cap (team)
    required_sections: tuple[str, ...]
    forbid_ticket_ids: bool
    forbid_mechanics: bool  # points / velocity / burndown wording


PROFILES: dict[str, AudienceProfile] = {
    "exec": AudienceProfile(
        "exec", 150, ("overall_rag", "top_risks", "ask"), True, True
    ),
    "programme": AudienceProfile(
        "programme", 400, ("overall_rag", "risks", "dependencies", "milestones"), True, False
    ),
    "team": AudienceProfile(
        "team", None, ("sprint_metrics", "ticket_progress", "blockers"), False, False
    ),
}

# A source-system ticket id, e.g. DRACO-412, ATLAS-12 (two+ leading alphanumerics).
TICKET_ID = r"[A-Z][A-Z0-9]+-\d+"

# Sprint-mechanics wording an exec report must not contain.
MECHANICS_TERMS = ("burndown", "velocity", "story points", "points")
