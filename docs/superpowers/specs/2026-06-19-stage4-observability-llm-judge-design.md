# Sprintsight: Design Spec, Stage 4 Observability + LLM-as-Judge (Epic SS-7)

Status: DRAFT 2026-06-19. Stage 4 (Observability + Evals, Epic SS-7). Eval-first.
Repo path: docs/superpowers/specs/2026-06-19-stage4-observability-llm-judge-design.md

## Plain-English summary (read this first)

So far our evals are deterministic: they check exact, known-true facts (right watermelon
label, right citation, right number). That works when there is one correct answer. Some
qualities have no single right answer, like "is this report readable and pitched right for
an exec?". This stage adds two things to cover that gap.

1. An LLM-as-judge readability eval. A second AI scores the report's prose against a tight
   rubric (clear? right tone? joined-up? clear ask?) and returns a structured score we can
   check mechanically. It does NOT re-check citations or numbers. That stays the
   deterministic eval's job.

2. Graph tracing. We extend the tracing we already have so a whole graph run becomes one
   recorded trace, with each node (retrieval, risk, report-writer) as a step underneath.
   Think flight recorder: when a report comes out odd, we replay the run instead of guessing.

Two guard rails keep this honest. First, before we trust the judge to grade reports, we
grade the judge: a small set of reports we already know are good or bad, and we assert the
judge agrees. Second, the judge is advisory at first (it records scores, it does not fail
the build), and only becomes a gate once that calibration check reliably passes.

## 1. What already exists (reused, not rebuilt)

- `sprintsight/evals/tracing.py`: a `Tracer` protocol with a `NoOpTracer` (used when Langfuse
  is unconfigured or not installed) and a `LangfuseTracer` adapter over the Langfuse v4 client.
  `get_tracer()` returns the real tracer only when `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`
  are set. CI never needs keys.
- `sprintsight/evals/harness.py`: the generic deterministic harness. `run_suite` already wraps
  each case in `tracer.span(...)`. Assertions are plain predicates (no LLM judging yet).
- `scripts/verify_langfuse.py`: an operational check that the keys work and a trace lands.
- `langfuse>=4` is already an optional (`eval`) dependency in pyproject.toml.
- `docs/evals/report-quality-eval.md` section 8 already reserved this slot: "Fuzzy prose
  grounding and tone quality: optional LLM-as-judge, NOT a gate, deferred to Stage 4."

So Stage 4 is not a greenfield build. It extends tracing from eval-case level to graph-node
level, and it adds the LLM-judge the report-quality spec already anticipated.

## 2. Scope

In scope:
- A readability judge: report in, structured 1-to-5 scores out, over four rubric dimensions.
- A calibration meta-eval: a handful of hand-labelled anchor reports, asserting the judge
  ranks obvious-good above obvious-bad.
- Graph tracing: one trace per graph run, with each node as a child span.
- An opt-in, key-gated `--judge` path on the report-eval runner. Advisory (non-gating) for now.
- Docs (this spec, an eval spec for the judge, ADR if tracing wiring changes), HANDOVER,
  LEARNING-LOG, and a Jira Story under SS-7.

Explicitly NOT in scope (YAGNI, "You Aren't Gonna Need It", meaning do not build it
speculatively):
- Promoting the judge to a hard build gate. That is a later step, taken only after the
  calibration check proves out.
- LLM-judging anything but the report (no judging the watermelon verdict or risk output).
- Langfuse dashboards, alerting, or score-uploading beyond traces landing.
- Any change to the deterministic report-quality or watermelon evals. They stay the gate.

## 3. The readability judge

### 3.1 Interface (the unit under test)
A judge is a callable: `judge(report, audience) -> JudgeScore`. It is the LLM-as-judge
counterpart to the deterministic checks in `sprintsight/evals/report.py`. Lives in a new
module `sprintsight/evals/judge.py`.

Output is structured (Anthropic structured output), not free text, so it is machine-scorable:

```json
{
  "clarity":        { "score": 4, "reason": "plain, minimal jargon" },
  "audience_fit":   { "score": 5, "reason": "outcome-first, no mechanics" },
  "coherence":      { "score": 4, "reason": "reads as one narrative" },
  "actionability":  { "score": 3, "reason": "ask is present but vague" }
}
```

### 3.2 Rubric (the four dimensions, confirmed with the product owner)
The judge scores only qualities the deterministic evals cannot measure. It must NOT re-check
citations, grounding, word caps, or section presence.

- clarity / plain English: clear and jargon-free, readable by a non-engineer. Penalise dense,
  abstract, convoluted prose.
- audience tone fit: does the register FEEL right (exec = outcome and decision; team =
  granular)? This goes beyond the deterministic word-count and section checks to judge tone.
- coherence / flow: one joined-up narrative versus a disconnected list of facts. Penalise
  abrupt jumps and repetition.
- actionability: for risk/exec reports, is the ask or decision-needed specific, or vague
  hand-waving? Does the reader know what to do next?

Each dimension is scored 1 (poor) to 5 (excellent). The judge prompt spells out what a 5
versus a 1 looks like for each dimension, so scores are anchored, not vibes.

### 3.3 Pass interpretation (advisory)
For each report, record the four scores and their mean. Provisional bar for "readable":
every dimension >= 3 AND mean >= 4. This bar is RECORDED, not enforced, until calibration
passes. The exact numbers can be tuned against the calibration anchors before any promotion
to a gate.

### 3.4 Model and isolation
- Provider: Anthropic (consistent with the stack), structured output.
- The judge uses its own prompt and role, separate from the report-writer, so the writer is
  never grading its own output with its own instructions ("marking its own homework").
- The judge call is key-gated: no API key means the judge eval is skipped, exactly like the
  existing live `--llm` report-writer path. CI never calls the API.

## 4. Calibration (grading the judge)

A small meta-eval that tests the judge itself, using the same pattern as every other eval:
known truth, scored.

- Anchor set: 3 to 4 hand-written reports with hand-assigned labels. At least one clearly
  good (crisp, audience-appropriate, clear ask) and one clearly bad (correct facts buried in
  jargon, or a waffly 500-word "exec summary", or an exec report with a vague ask).
- Assertions: the judge scores each good anchor above the bar and each bad anchor below it,
  on the dimension each anchor is designed to exercise. If the judge cannot separate obvious
  good from obvious bad, it is not trustworthy and must not gate.
- The anchors are fixtures (hand-authored, not drawn from the live writer) so the calibration
  is stable and independent of report-writer changes.

This meta-eval is what lets us defend the judge: "how do you know the AI grader is right?
Because we tested the grader."

## 5. Graph tracing

Extend the existing tracer (no new tracing tech) so a graph run is observable end to end.

- One parent trace per `run`/`build_graph` invocation.
- Each of the three nodes (retrieval, risk, report-writer) becomes a child span recording
  its inputs slice and its returned slice, plus timing.
- The graph builder takes an optional tracer; default is `NoOpTracer`, so the offline path
  and CI are unchanged and key-free.
- Reuses the `Tracer` protocol and `get_tracer()` already in `tracing.py`. If wiring a tracer
  through the graph changes a previously locked decision, record it in a short ADR
  (Architecture Decision Record, a one-page note capturing a decision and its reason).

## 6. How it runs (CI-safe)

- Default eval run: deterministic only, fully offline, no keys, unchanged. Still the build gate.
- `--judge` flag on the report-eval runner: adds the readability judge pass. Key-gated; with
  no key it prints a skip notice and exits success. Advisory: judge scores are reported but do
  not change the suite's pass/fail.
- Tracing: off by default (no-op). On only when Langfuse keys are present.

This preserves the project invariant: the default path is offline and deterministic, CI never
calls the API, live paths are opt-in and key-gated.

## 7. Eval-first order of work

The deliverable here is itself an eval, so eval-first is satisfied by construction. Within the
build, the known-truth comes before the code that must satisfy it:

1. Write the judge rubric and the calibration anchors (the known truth) first.
2. Write the calibration meta-eval asserting the judge ranks the anchors correctly. RED until
   the judge exists.
3. Implement the judge until the calibration meta-eval is GREEN.
4. Wire the opt-in `--judge` path and the graph-node tracing.

## 8. Components and boundaries

- `sprintsight/evals/judge.py` (new): the judge callable, the structured `JudgeScore` shape,
  the rubric prompt. Depends on the Anthropic client and the report contract. Knows nothing
  about Langfuse or the graph.
- calibration anchors + meta-eval (new): fixtures plus assertions over the judge. Depends on
  the judge only.
- `sprintsight/evals/tracing.py` (extend) and the graph builder (extend): node-level spans.
  The graph depends on the `Tracer` protocol, not on Langfuse directly.
- report-eval runner (extend): the opt-in `--judge` path. Depends on the judge and the
  existing report suite.

Each unit is testable alone: the judge without the graph, the tracing without the judge, the
calibration without Langfuse.

## 9. Risks and mitigations

- Judge is wrong / flaky: mitigated by advisory-first plus the calibration gate before any
  promotion. A wrong judge cannot block a good build until we trust it.
- Judge grades its own homework: mitigated by a separate prompt/role from the writer, and by
  judging only prose qualities the writer is not deterministically optimising for.
- Cost / non-determinism in CI: mitigated by key-gating. CI runs deterministic-only and offline.
- Tracing leaks data to Langfuse: spans carry report text and team ids. Langfuse is
  ZDR (zero data retention, the provider does not keep the data) and opt-in, off by default.
  Flag in the ADR if any new field is sent; keep least-data.

## 10. Done means

- `judge.py` exists; calibration meta-eval is GREEN on a credible keyed run.
- Graph runs emit one trace with three node spans when keyed; no-op and unchanged otherwise.
- `--judge` path runs advisory and key-gated; default eval run untouched and still gating.
- Deterministic evals (watermelon, report-quality) still GREEN and still the gate.
- Docs updated (this spec, judge eval spec, ADR if needed), HANDOVER + LEARNING-LOG current,
  Jira Story under SS-7 moved through In Review to Done with a completion comment.

## 11. What this unblocks

- A defensible quality signal for the soft qualities deterministic evals cannot measure.
- End-to-end visibility of a graph run, so eval failures can be diagnosed by replay.
- A calibrated path to later promote readability from advisory to a real build gate.
