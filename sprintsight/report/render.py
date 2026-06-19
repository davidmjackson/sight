"""Human-readable markdown rendering for a Report.

The keys in `Report.sections` are the machine contract (audience.py
`required_sections`, asserted by the report-quality eval), so they stay
snake_case. This module is the SINGLE place that turns those keys into the
human headings a reader (or the LLM-judge) should see. One renderer, reused by
the judge and any future display surface, instead of heading logic buried in
the eval.
"""

from sprintsight.report.contract import Report

SECTION_TITLES: dict[str, str] = {
    "overall_rag": "Overall status",
    "top_risks": "Top risks",
    "ask": "Recommended next step",
    "risks": "Risks",
    "dependencies": "Dependencies",
    "milestones": "Milestones",
    "sprint_metrics": "Sprint metrics",
    "ticket_progress": "Ticket progress",
    "blockers": "Blockers",
}


def heading_for(key: str) -> str:
    """Human title for a section key; unknown keys fall back to the key unchanged."""
    return SECTION_TITLES.get(key, key)


def render_report_markdown(report: Report) -> str:
    """Render a Report's sections as markdown with human headings."""
    if not report.sections:
        return "(no sections)"
    return "\n\n".join(f"## {heading_for(k)}\n{v}" for k, v in report.sections.items())
