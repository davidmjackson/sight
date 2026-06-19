"""LLM-as-judge readability eval (Stage 4, SS-7).

Scores a finished Report on four prose qualities the deterministic report-quality eval
cannot measure: clarity, audience tone fit, coherence, actionability. It does NOT re-check
citations, grounding, word caps, or section presence; those stay report.py's job.

The grader (the Anthropic call) is injected, mirroring report/llm_writer.py: tests run with
a fake and CI never calls the API. Advisory by design: callers read JudgeScore.passes but it
does not gate the build until the calibration meta-eval proves the judge (see calibration.py).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sprintsight.report.contract import Report
from sprintsight.report.render import render_report_markdown

DEFAULT_MODEL = "claude-sonnet-4-6"  # same family as the writer; judge has its own prompt/role

DIMENSIONS = ("clarity", "audience_fit", "coherence", "actionability")

# Advisory pass bar (spec section 3.3): every dimension >= 3 AND mean >= 3.5.
# Tuned against the live calibration run (2026-06-19): the per-dimension floor cleanly
# rejects all three bad anchors, while a strong report (good-exec scored 4/4/3/4, mean 3.75)
# must clear the bar. mean >= 4 wrongly failed it; 3.5 admits it with margin.
MIN_PER_DIMENSION = 3
MIN_MEAN = 3.5

# (system_prompt, user_prompt, schema) -> {dimension: {"score": int, "reason": str}}
Grader = Callable[[str, str, dict[str, Any]], dict[str, Any]]
JudgeFn = Callable[[Report, str], "JudgeScore"]

_SYSTEM = (
    "You are a delivery-report editor grading PROSE QUALITY only. You are given a status "
    "report and its target audience. Score four dimensions from 1 (poor) to 5 (excellent). "
    "Do NOT check facts, numbers, or citations; assume those are already verified. "
    "Dimensions: clarity (plain English, jargon-free, readable by a non-engineer); "
    "audience_fit (register matches the audience: exec = outcome and decision, team = granular); "
    "coherence (one joined-up narrative, not a disconnected list; no repetition); "
    "actionability (the report surfaces the most material item and a specific, grounded "
    "recommended focus or next step, so the reader knows what to watch or decide; a grounded "
    "recommendation is fully sufficient, so do NOT require or reward an invented owner, calendar "
    "date, or manufactured decision, and do not penalise their absence when the source data does "
    "not contain them). "
    "A 5 is exemplary, a 1 is unacceptable. Be a strict grader."
)


@dataclass(frozen=True)
class JudgeScore:
    """Structured readability score for one report. Scores are 1 (poor) to 5 (excellent)."""

    scores: dict[str, int]
    reasons: dict[str, str]

    @property
    def mean(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0

    @property
    def passes(self) -> bool:
        if set(self.scores) != set(DIMENSIONS):
            return False
        return all(v >= MIN_PER_DIMENSION for v in self.scores.values()) and self.mean >= MIN_MEAN


def _user_prompt(report: Report, audience: str) -> str:
    body = render_report_markdown(report)
    return f"Audience: {audience}.\nReport for team {report.team}:\n\n{body}"


def _schema() -> dict[str, Any]:
    cell = {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 5},
            "reason": {"type": "string"},
        },
        "required": ["score", "reason"],
    }
    return {
        "type": "object",
        "properties": {d: cell for d in DIMENSIONS},
        "required": list(DIMENSIONS),
    }


def make_judge(grade: Grader | None = None, model: str = DEFAULT_MODEL) -> JudgeFn:
    grader = grade or _anthropic_grader(model)

    def judge(report: Report, audience: str) -> JudgeScore:
        raw = grader(_SYSTEM, _user_prompt(report, audience), _schema())
        scores: dict[str, int] = {}
        reasons: dict[str, str] = {}
        for d in DIMENSIONS:
            cell = raw.get(d, {}) if isinstance(raw, dict) else {}
            if not isinstance(cell, dict):
                cell = {}
            scores[d] = int(cell.get("score", 0))
            reasons[d] = str(cell.get("reason", ""))
        return JudgeScore(scores=scores, reasons=reasons)

    return judge


def _anthropic_grader(model: str) -> Grader:
    """Real grader: Anthropic Messages API with tool-use structured output.

    Mirrors report/llm_writer.py:_anthropic_completer. ZDR is an account-level config, not a
    per-request header, so no extra_headers here.
    """

    def grade(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        import anthropic  # lazy: only needed on the live path

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        tool = {
            "name": "emit_scores",
            "description": "Return the four readability scores.",
            "input_schema": schema,
        }
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit_scores"},
            messages=[{"role": "user", "content": user}],
        )
        for block in msg.content:
            if block.type == "tool_use" and block.name == "emit_scores":
                return block.input
        return {}

    return grade
