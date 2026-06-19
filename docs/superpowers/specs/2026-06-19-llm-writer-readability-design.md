# LLM Writer Readability Design

> Plain-English summary (for a non-engineer): Our automated "does this read well?" check (an
> AI judge) scored both our real status reports below bar. The fix is to teach the AI report
> writer to write more usefully: lead with the one thing to watch, give a concrete watch-point
> instead of vague reassurance, stop repeating itself, and talk at the right level for the
> audience. We are not inventing any facts and not lowering the bar. Because the judge is itself
> an AI and its score wobbles run to run, we also start scoring each report three times and
> taking the middle number, so we can actually tell whether the fix worked.

**Date:** 2026-06-19
**Arc:** LLM writer readability (Epic SS-7, follow-on to the compose-writer-readability arc)
**Branch:** `llm-writer-readability-arc`
**Status:** Design approved; implementation plan to follow.

## Why this arc

The Stage 4 LLM-as-judge readability eval, run live on our real reports, scored both below the
advisory bar (every dimension >= 3 and mean >= 3.5):

- boreas-exec: mean 2.75 (one live sample)
- atlas-programme: mean 3.00

The previous arc (compose-writer-readability) fixed the deterministic `compose` writer and
recalibrated the judge's `actionability` definition. `compose` is clean and grounded but terse,
and it plateaus (boreas-exec 3.0, atlas-programme 2.2), blocked on `audience_fit` because it
cannot ground a business-impact narrative. The LLM writer can write that narrative. This arc
tunes the LLM writer's prose to clear the bar on both audiences.

### What the judge actually complained about (live evidence, 2026-06-19)

| Where | Score | What the judge wanted |
|-------|-------|------------------------|
| exec audience_fit | 2 | Do not list three risks at equal weight. Say which one matters most and what is at stake. |
| exec actionability | 2 | "No decision needed, escalate if any slips" puts the work back on the exec. Surface the single most material risk and what a slip would look like. |
| programme actionability | 2 | "The team is aware and planning accordingly" / "alignment will be maintained" is passive reassurance. Give a concrete watch-point. |
| programme coherence | 3 | Overall-status and Milestones repeat each other; reads as four loose paragraphs. |
| programme audience_fit | 3 | Raw velocity (12) and carry-over points (5) are too team-level for a programme reader. |

The single common thread: lead with the most material item, give a concrete grounded watch-point,
cut repetition, match the register. None of it requires inventing facts.

## Decisions taken during brainstorming

1. **Fabrication boundary (David's call): frame, never rank by invented severity.** The writer
   may lead with a risk and give a grounded watch-point drawn from the risk's own wording, but
   must not assert a severity ranking it cannot support. The items already arrive in logged
   order, so "lead with the first listed item" needs no invented ranking. Language stays "the one
   to watch", never "highest severity".
2. **Arc scope (David's call): writer prose plus stable measurement.** Improve the LLM writer
   prompt and measure with a 3-sample judge median. The judge stays advisory. Promotion to a CI
   gate is a separate, later decision once the judge reads stably.
3. **Approach (David's call): instructions plus one worked exemplar (Approach B).** Few-shot
   teaches the grounded-watch-point style the judge is asking for far more reliably than
   instructions alone, and directly attacks the passive-reassurance failure.

## Architecture

The change sits behind the existing `ReportWriter` seam. We touch the LLM writer's prompt only.
The deterministic core (`_grounded_facts`), the `compose` writer, the section contract in
`audience.py`, and the judge's rubric all stay exactly as they are.

Three pieces:

1. **Writer prompt** (`sprintsight/report/llm_writer.py`, `_SYSTEM` and `_user_prompt`).
2. **Stable measurement** (`sprintsight/evals/judge.py` plus `scripts/run_report_eval.py`).
3. **Deterministic anchor** (unit tests that pin the prompt content), since neither writer nor
   judge can be asserted exactly in CI.

Guiding principle: `compose` stays the deterministic CI gate and offline fallback. The LLM writer
is the thing being tuned. The judge is advisory measurement, not a gate.

### 1. Writer prompt change

Four directives added to `_SYSTEM`, one worked exemplar, one line added to `_user_prompt`.

New `_SYSTEM` directives:

1. **Lead with the first item.** The risks and dependencies are already in priority order; lead
   with the first as the item to watch. Do not claim a severity ranking and do not use words like
   "highest", "most severe", or "biggest". Frame it as "the one to watch".
2. **Grounded watch-point, no passive reassurance.** For each risk and dependency, give a concrete
   watch-point taken from that item's own wording (what to monitor, or what a slip would look like
   and why it matters). Never write passive reassurance such as "the team is aware", "planning
   accordingly", or "alignment will be maintained".
3. **No repetition.** Do not repeat the same point in more than one section.
4. **Register.** Exec: business outcome and the single thing to watch, not a flat list of
   equal-weight risks. Programme: trajectory and decision triggers; do not quote raw velocity or
   carried-over point counts in the prose.

Worked exemplar (neutral placeholder data so no facts can leak into real output):

> Bad (passive, vague): "The team is aware of the vendor dependency and alignment will be
> maintained."
> Good (grounded watch-point): "Vendor API rate limits are untested at peak load. Watch whether
> the load test clears before the launch gate, since a failure would push the integration
> milestone."

One line added to `_user_prompt`: "The first risk listed is your lead item to watch."

Grounding safeguards:

- The "drop raw velocity/points from programme prose" directive is safe for the deterministic
  gate, because those numbers live in the separate cited `claims`, which always render regardless
  of prose. The gate checks claims, not prose wording.
- The existing validator `_section_violates` still falls anything bad back to `compose` prose, so
  the deterministic eval holds by construction no matter what the LLM returns.

### 2. Stable measurement

New helper in `judge.py`:

```
sample_judge(judge, report, audience, n=3) -> JudgeScore
```

Calls the judge `n` times and returns a `JudgeScore` whose each dimension is the median of that
dimension's `n` scores. Reusing `JudgeScore` keeps `.mean` and `.passes` working unchanged on the
median result. The reasons field keeps the last sample's reasons (enough for a human to read why).
If a sample throws, that sample is dropped and the median is taken over the rest.

Why median: median of 3 shrugs off a single outlier run (the swing that took exec from 4.2 to
2.75). It is the cheap standard way to de-noise an LLM judge without a large sampling budget.

`scripts/run_report_eval.py` (`_run_judge_pass`): runs `sample_judge` per case and prints the
median plus the min-to-max range per dimension. Still advisory, still key-gated, never changes the
exit code. Cost: 3 judge calls per report, 6 per measurement run (two reports). Trivial.

### 3. Deterministic anchor (tests)

Because both writer and judge are LLMs, CI cannot assert a quality score. The CI-safe guards are:

- A unit test that the built `_SYSTEM` prompt contains each directive marker (lead-item,
  watch-point, banned-passive phrasing, register) and that `_user_prompt` contains the lead-item
  line. This pins the prompt so a future edit cannot silently drop a directive.
- The existing deterministic report eval staying green (keys, caps, ticket ids, mechanics).

## Testing

New tests (all deterministic, CI-safe):

1. `tests/test_judge.py`: `sample_judge` with a fake grader returning a fixed sequence returns the
   per-dimension median (e.g. `[2,4,4]` gives `4`); single-sample and sample-with-error behave
   sanely.
2. `tests/test_llm_writer.py`: the `_SYSTEM` prompt contains each directive marker and
   `_user_prompt` contains "first risk listed is your lead item".

Regression guard (unchanged, must stay green): full `pytest`, `ruff check .`, watermelon eval 4/4,
report eval 4/4.

## Success criteria

Measured live on the key-gated path, not CI-gated: the 3-sample judge median on the LLM writer
clears the advisory bar (every dimension >= 3 and mean >= 3.5) on both boreas-exec and
atlas-programme.

### Honesty clause

If a dimension cannot reach 3 without inventing a fact, owner, date, or ranking, we stop and
report it rather than rewording to chase the score. The rubric was corrected once last arc and is
not touched again. If grounded prose genuinely cannot clear the bar, that is a finding about the
bar or the data for David to decide on, not something to quietly game.

## Error handling

- LLM writer failure already degrades to `compose` prose (unchanged).
- A judge sample that throws is dropped; the median is taken over the rest. The script's existing
  try/except keeps the advisory pass from ever breaking the run.

## Non-goals (scope guards)

- No judge gate promotion this arc.
- No judge rubric change.
- No section-key or contract change in `audience.py`.
- No edits to `compose` (`sprintsight/report/writer.py`); it stays the deterministic gate and
  fallback.

## Files touched

- `sprintsight/report/llm_writer.py` (`_SYSTEM`, `_user_prompt`, exemplar constant)
- `sprintsight/evals/judge.py` (`sample_judge`)
- `scripts/run_report_eval.py` (`_run_judge_pass` median + range)
- `tests/test_llm_writer.py`, `tests/test_judge.py`
- Docs: `HANDOVER.md`, this spec, a `Learning queue` flag line in `HANDOVER.md`

## Learning-log flag

Per CLAUDE.md, Claude Code does not write `LEARNING-LOG.md`. Append one line to the HANDOVER
`Learning queue` for the planning thread to turn into an entry. Candidate concept: "De-noising an
LLM judge by sampling and taking the median, and why a noisy judge cannot be a gate yet."
