"""LLM-backed report writer behind the `ReportWriter` seam (Stage 2 arc 2).

Hybrid: the deterministic core (`_grounded_facts`) owns numbers, RAG status, and the
cited `claims`; the LLM authors only section prose. A validator falls violating or
over-cap sections back to `compose`'s prose, so every report-eval assertion holds by
construction. The Anthropic completer is injected, so CI/tests run with a fake.
"""

import re
from collections.abc import Callable
from typing import Any

from sprintsight.report.audience import (
    MECHANICS_TERMS,
    TICKET_ID,
    AudienceProfile,
    contains_mechanics,
)
from sprintsight.report.contract import Report
from sprintsight.report.writer import (
    Facts,
    ReportWriter,
    _compose_sections,
    _grounded_facts,
)

DEFAULT_MODEL = "claude-sonnet-4-6"  # confirmed via claude-api skill; verified live 2026-06-18

# (system_prompt, user_prompt, output_schema) -> {section_key: prose}
Completer = Callable[[str, str, dict[str, Any]], dict[str, str]]

_SYSTEM = (
    "You write concise, audience-tuned delivery status prose. You are given already-"
    "verified facts. Write only from those facts. Never invent numbers, dates, or ticket "
    "ids. Return one short paragraph per requested section.\n"
    "Lead with the one to watch: the risks and dependencies you are given are already in "
    "priority order, so treat the first one as the item to watch. Do not claim a severity "
    "ranking and do not use the words 'highest', 'most severe', or 'biggest'.\n"
    "For each risk and dependency, give a concrete watch-point taken from that item's own "
    "wording: what specifically to monitor, or what a slip would look like and why it "
    "matters. Never write passive reassurance such as 'the team is aware', 'planning "
    "accordingly', or 'alignment will be maintained'.\n"
    "Do not repeat the same point in more than one section.\n"
    "For an exec audience, give the business outcome and the single thing to watch, not a "
    "flat list of equal-weight risks. For a programme audience, give trajectory and decision "
    "triggers; do not quote raw velocity or carried-over point counts in the prose.\n"
    "Example. Bad (passive, vague): 'The team is aware of the vendor dependency and "
    "alignment will be maintained.' Good (grounded watch-point): 'Vendor API rate limits "
    "are untested at peak load. Watch whether the load test clears before the launch gate, "
    "since a failure would push the integration milestone.'"
)


def _user_prompt(f: Facts) -> str:
    p = f.profile
    lines = [
        f"Team: {f.team}. Audience: {p.name}.",
        f"Overall reported status (RAG): {f.rag}.",
        f"Risks: {f.risks or 'none logged'}.",
        f"Dependencies: {f.deps or 'none logged'}.",
        f"Looking ahead: {f.looking_ahead or 'n/a'}.",
    ]
    if f.metrics is not None:
        m = f.metrics
        lines.append(
            f"Metrics: committed {int(m.committed)}, completed {int(m.completed)}, "
            f"velocity {int(m.velocity)}, carry-over {int(m.carry_over)}."
        )
    if p.max_words and p.max_words <= 200:
        # A tight cap (exec): the report-level cap discards over-length prose wholesale, so
        # press the writer to land well under it. Generous caps (programme) get a gentle nudge
        # only, so we do not strip the narrative that earns audience-fit.
        target = int(p.max_words * 0.75)
        lines.append(
            f"HARD WORD LIMIT: the entire report, including the figures, must stay under "
            f"{p.max_words} words. Aim for about {target} words. Lead with the item to watch and "
            "its watch-point in full; compress every secondary item to a single clause."
        )
    elif p.max_words:
        lines.append(f"Keep the whole report comfortably under {p.max_words} words.")
    else:
        lines.append("Word budget: no strict cap, but stay concise.")
    if p.forbid_ticket_ids:
        lines.append("Do NOT mention any ticket ids (e.g. ABC-123).")
    if p.forbid_mechanics:
        lines.append(f"Do NOT mention sprint mechanics: {', '.join(MECHANICS_TERMS)}.")
    lines.append(f"Write these sections: {', '.join(p.required_sections)}.")
    lines.append("The first risk listed is your lead item to watch.")
    return "\n".join(lines)


def _schema(profile: AudienceProfile) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "sections": {
                "type": "object",
                "properties": {k: {"type": "string"} for k in profile.required_sections},
                "required": list(profile.required_sections),
            }
        },
        "required": ["sections"],
    }


def _section_violates(text: str, profile: AudienceProfile) -> bool:
    if not text.strip():
        return True
    # The system prompt forbids inventing ticket ids for all audiences; finding one always
    # signals misbehaviour — fall back regardless of whether the profile explicitly forbids them.
    if re.search(TICKET_ID, text):
        return True
    if profile.forbid_mechanics and contains_mechanics(text):
        return True
    return False


def _rendered_words(sections: dict[str, str], claims: list) -> int:
    # Mirror the eval's _render: section values + claim texts, whitespace-split.
    text = " ".join(list(sections.values()) + [c.text for c in claims])
    return len(text.split())


def make_llm_writer(complete: Completer | None = None, model: str = DEFAULT_MODEL) -> ReportWriter:
    completer = complete or _anthropic_completer(model)

    def write(inputs: dict[str, Any]) -> Report:
        f = _grounded_facts(inputs)
        if f.insufficient:
            return Report(team=f.team, audience=f.audience, insufficient_evidence=True)

        fallback = _compose_sections(f)
        try:
            prose = completer(_SYSTEM, _user_prompt(f), _schema(f.profile))
        except Exception:  # noqa: BLE001 - any LLM failure degrades to the deterministic prose
            prose = {}
        sections_in = prose.get("sections", prose) if isinstance(prose, dict) else {}

        sections: dict[str, str] = {}
        for key in f.profile.required_sections:
            text = sections_in.get(key, "") if isinstance(sections_in, dict) else ""
            sections[key] = fallback[key] if _section_violates(text, f.profile) else text

        # Report-level cap: the whole rendered report must respect the audience word cap.
        if f.profile.max_words and _rendered_words(sections, f.claims) > f.profile.max_words:
            sections = fallback

        return Report(team=f.team, audience=f.audience, sections=sections, claims=f.claims)

    return write


def _anthropic_completer(model: str) -> Completer:
    """Real completer: Anthropic Messages API with tool-use structured output.

    NOTE: ZDR (zero data retention) is an account/org-level configuration, not a
    per-request header. No extra_headers are needed here; enable ZDR in the Anthropic
    console for your organisation if required.
    """

    def complete(system: str, user: str, schema: dict[str, Any]) -> dict[str, str]:
        import anthropic  # lazy: only needed on the live path

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        tool = {
            "name": "emit_report",
            "description": "Return the report sections.",
            "input_schema": schema,
        }
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit_report"},
            messages=[{"role": "user", "content": user}],
        )
        for block in msg.content:
            if block.type == "tool_use" and block.name == "emit_report":
                return block.input  # {"sections": {...}}
        return {}

    return complete
