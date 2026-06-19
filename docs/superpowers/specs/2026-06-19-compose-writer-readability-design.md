# Design: compose writer readability arc (SS-7)

Plain-English summary (read this first)

We built an LLM-as-judge that reads our status reports the way a person would and scores
them on how well they read. When we pointed it at our real reports, they scored below the
bar (around 2 out of 5) even though they pass every automated check we had before. The judge
is right: the reports read like internal team notes. This arc fixes the deterministic report
writer (`compose`) so the judge goes green, without inventing any facts. Three targeted fixes,
each aimed at one thing the judge marked down.

## 1. Why

The deterministic report-quality eval checks structure (citations, grounding, word count,
sections present). It is blind to whether a report actually reads well. The Stage 4 judge
(`sprintsight/evals/judge.py`) added that missing measure and is currently RED on our real
cases:

- boreas-exec: ~2.2, atlas-programme: ~2.0
- audience_fit 2 ("reads like an internal team note")
- coherence 2 ("disconnected fragments, a checklist not a narrative")
- actionability 1 ("a dead end, no forward guidance")

The judge already exists, so the eval this arc must pass already exists. This is the
eval-first loop: a real eval is RED, we make it green for the right reasons.

## 2. Scope

In scope: the deterministic `compose` writer (`sprintsight/report/writer.py`). It is the CI
gate and the offline fallback, so it sets the floor for every report and is fully under our
control.

Out of scope this arc:
- The LLM writer's prompt (`sprintsight/report/llm_writer.py`). It inherits the human headings
  for free via the shared renderer, but we do not tune its prompt here. Separate lever, later.
- Promoting the judge from advisory to a CI gate. Stays a later step (needs the live key,
  which CI does not have).

## 3. The three fixes (all in compose / the shared renderer)

### 3.1 Human headings (clarity, audience_fit)

The section keys (`overall_rag`, `top_risks`, `ask`, etc.) double as the machine contract:
they are listed in `audience.py` as `required_sections` and asserted in `test_report_writer`.
So we do NOT rename the keys.

Instead, add a single shared renderer, `render_report_markdown(report)`, that maps each key to
a human title and emits markdown. The judge reads through this renderer instead of printing raw
keys (today `judge.py:_user_prompt` does `## {k}` with the raw key).

Title map (one place, covers all profiles):

| key             | title                |
|-----------------|----------------------|
| overall_rag     | Overall status       |
| top_risks       | Top risks            |
| ask             | Recommended next step|
| risks           | Risks                |
| dependencies    | Dependencies         |
| milestones      | Milestones           |
| sprint_metrics  | Sprint metrics       |
| ticket_progress | Ticket progress      |
| blockers        | Blockers             |

Renderer placement: a new small module `sprintsight/report/render.py` (one purpose: turn a
`Report` into human-readable markdown). The judge imports it. This pulls display logic out of
the eval and gives us one human-facing renderer for any future display surface.

### 3.2 Split run-together risks (coherence)

Today `compose` joins multiple risks/dependencies/blockers with `" ".join(...)`, producing one
jammed blob ("...timezone edge cases Holiday cover..."). Render each item as its own line in a
list within the section value, so the judge sees distinct items, not a fragment soup. Applies
everywhere compose joins a multi-item list: exec `top_risks`, programme `risks` and
`dependencies`, team `blockers`.

The section keys and the underlying `claims` (with their citations) are unchanged; only the
prose string formatting changes.

### 3.3 Forward-looking ask, exec only (actionability)

Replace the hardcoded dead end `"Decision needed: none this period."`. Rule, grounded only in
data we already parsed (the RAG status and the logged risks):

- amber or red, with risks logged: name the count and the single most material logged risk,
  and recommend confirming it is owned before sprint close. Example:
  "Recommended focus: 2 risks logged. Most material: Digest scheduler timezone edge cases.
  Confirm it is owned before sprint close."
- green, no risks: "No decision needed this period; delivery on track."

"Most material" = the first risk in the logged order. There is no severity field on the RAID
rows to sort on, so we take the logged order as-is and do not invent a ranking. (If we later
add a severity field, the rule sorts on it. To confirm during build: check the RAID fixtures
do not list risks in a misleading order; if they do, fall back to "the risks above" without
singling one out.) The recommendation is recommend-only prose, not a write, so
human-in-the-loop is intact.

Only the exec profile has an `ask` section. Programme already carries a forward-looking
`milestones` line; team carries `blockers`. Neither gets a synthetic ask.

## 4. Guardrails (what must not break)

- Section keys stay identical. The deterministic report-quality eval (`evals/report.py`) and
  `test_report_writer` stay green.
- No new facts. The ask references only risks already logged and the RAG status already parsed.
  No invented owners, dates, or decisions.
- `null_writer` and the LLM writer seam are untouched.

## 5. Eval-first verification and Done

Definition of Done:

1. Deterministic gate stays green offline: watermelon eval 4/4 and report-quality eval 4/4
   (these are the CI gate). Run both after the change.
2. Target eval goes green live: the advisory judge, run on the real exec and programme cases
   via `scripts/run_report_eval.py --judge` (and `--llm --judge` as a sanity check), moves from
   ~2.0 to every dimension >= 3 and mean >= 3.5.
3. Honesty clause: if any dimension stays at 2 for a reason we cannot fix without fabricating,
   stop and report it rather than reword to game the judge. We do not promote the judge
   advisory->gate in this arc.

## 6. Build approach

Single focused Story, a new SS-7 child (continues the readability thread). Built eval-first via
the normal SDD flow (fresh implementer plus independent reviewer per task). New unit tests for
the renderer and the forward-looking ask rule. Existing tests must stay green.
