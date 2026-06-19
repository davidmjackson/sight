"""Audience profiles (report-quality-eval.md §4, LOCKED).

Single source of truth for length caps, required section keys, and forbidden detail
markers. Read by both the composer (to shape output) and the eval (to score audience fit).
"""

import re
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

# Match a mechanics term only as a standalone word or phrase, never inside a larger token.
# The lookarounds exclude word characters AND hyphens on both sides, so genuine sprint
# wording ("38 points", "story points", "velocity") is caught while unrelated compounds
# ("watch-points", "touchpoints", "checkpoints") are not. Substring matching used to reject
# the LLM writer's own "watch-points" prose, forcing a fallback to terse compose output.
_MECHANICS_RE = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(t) for t in MECHANICS_TERMS) + r")(?![\w-])",
    re.IGNORECASE,
)


def contains_mechanics(text: str) -> bool:
    """True if the text uses sprint-mechanics wording as a standalone word or phrase."""
    return bool(_MECHANICS_RE.search(text))
