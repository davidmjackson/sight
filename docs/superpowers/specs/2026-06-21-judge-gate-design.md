# Promote the readability judge to a gate (live check only)

Date: 2026-06-21
Stage: 4 (Observability + Evals, Epic SS-7)
Status: design — awaiting review

## Plain-English summary (read this first)

We have an AI "judge" that scores how readable a finished status report is. Today it only
ever *prints* its scores; it can never fail anything. This change lets it **block a merge**,
but only on the command a person runs by hand before merging, never in the automated cloud
checker (CI). CI stays exactly as it is: offline, free, deterministic.

Two reasons we kept the judge advisory until now, and how this design handles them:

1. **CI runs offline.** The judge needs the paid Anthropic API and the secret key. CI has
   neither and never calls out. So we are NOT touching CI. We add the gate only to the
   manual, key-holding run.
2. **The judge wobbles.** One report's "coherence" score sits right on the pass line (3 of
   5), so an unlucky run could fail it with no code change. We guard against that with a
   stronger de-noiser (5-sample median) plus a trust check (the judge must pass its own
   calibration meta-eval before it is allowed to block anything).

Net effect: a person running the pre-merge check gets a real red light when a report reads
below bar; nothing that is green today can turn red from this; the whole thing is reversible
by deleting one flag.

## Decision

Add a new flag `--judge-gate` to `scripts/run_report_eval.py`. It runs the LLM-as-judge
readability pass and lets it fail the run. The existing `--judge` flag stays advisory
(prints scores, never fails). CI invocation (no flags) is untouched.

This is "Option A" from brainstorming: gate the live check only. "Option B" (putting the
key into CI and blocking pushes automatically) is explicitly out of scope.

## Design

### Flag behaviour

- `run_report_eval.py` (no flags) — unchanged. Deterministic report eval is the CI gate.
- `run_report_eval.py --judge` — unchanged. Advisory readability scores, sampled 3x, exit
  code never affected.
- `run_report_eval.py --judge-gate` — NEW. Requires a real `ANTHROPIC_API_KEY`
  (`sk-ant-`, len >= 50); exits 2 immediately if absent, matching the existing `--llm`
  guard (a deliberate gate run with no key is an error, not a silent skip). Runs the judge
  and can fail the run.

`--judge-gate` implies the deterministic report eval still runs and still counts: the
process exit code is non-zero if EITHER the deterministic eval fails OR the judge gate
blocks. The two are independent and combine with logical OR.

### The gate decision (pure, testable, no API)

A new pure function decides pass/fail from already-collected data, so it is unit-testable
offline with no Anthropic call:

```
judge_gate_decision(
    medians: list[tuple[str, JudgeScore | None]],   # (case_name, median score) per eval case
    calibration_ok: bool,
) -> GateDecision                                    # {blocks: bool, reasons: list[str]}
```

Rules, in order:

1. **Calibration is the trust gate.** If `calibration_ok` is False, the gate does NOT block
   (`blocks=False`) regardless of report scores. It prints a loud "judge not trusted this
   run — advisory only" line. Rationale: a judge that cannot separate its own hand-labelled
   good/bad anchors today must not be allowed to fail a build today. This is the promotion
   precondition the handover named.
2. **Infra failure never blocks.** A case whose median is `None` because every judge sample
   errored is reported loudly but does NOT block. We never turn a build red because the
   judge could not run. (Insufficient-evidence reports are also `None`/skipped and likewise
   do not block — they are a legitimate n/a, not a readability failure.)
3. **Otherwise block on a real below-bar score.** If calibration passed, the gate blocks if
   any scorable case's median `.passes` is False (i.e. a dimension < 3 or mean < 3.5, per
   the existing bar in `judge.py`). The rubric and bar are unchanged.

### Wiring in the script

- Extract the per-case median computation currently inlined in `_run_judge_pass` into a
  shared helper that returns structured `(case_name, JudgeScore | None, lo/hi spans)` rather
  than only printing. Both the advisory pass (`--judge`, n=3) and the gate (`--judge-gate`,
  n=5) call it; the only difference is the sample count and what the caller does with the
  result.
- On `--judge-gate`: first run `run_calibration(make_judge())` and set
  `calibration_ok = (report.pass_rate == 1.0)`. Then score the eval cases at n=5, build the
  medians list, call `judge_gate_decision`, print the scoreboard and the verdict, and fold
  `decision.blocks` into the process exit code.
- Sample count: gate path n=5 (tighter median; a genuine 3 needs three of five samples to
  drop to <=2 to fail — very unlikely). Advisory path stays n=3. `n` stays a parameter so it
  is tunable without a code change in spirit.

### What does NOT change

Deterministic report eval, watermelon eval, CI workflow, the judge rubric (`_SYSTEM`), the
pass bar (`MIN_PER_DIMENSION`, `MIN_MEAN`), the LLM writer, `compose`. The judge stays
advisory everywhere except the new explicit `--judge-gate` invocation.

## Testing (eval-first; offline; CI-safe)

The new behaviour gets tests BEFORE the wiring, all with fake graders so CI never calls the
API:

1. `judge_gate_decision` — the core unit:
   - all medians pass + `calibration_ok=True` → `blocks=False`.
   - one median below bar + `calibration_ok=True` → `blocks=True`.
   - one median below bar + `calibration_ok=False` → `blocks=False` (calibration gate).
   - a `None` median (infra fail / insufficient evidence) alongside passing medians +
     `calibration_ok=True` → `blocks=False` (infra never blocks); but a `None` PLUS a real
     below-bar case still → `blocks=True`.
2. (If cheap) a thin script-level test driving the decision with a fake judge to confirm the
   exit code folds in `blocks`. Keep to the pure function if the script path needs the live
   key guard; do not add an API-touching test.

Existing suites stay green: deterministic report eval 4/4, watermelon 4/4, ruff clean.

## Out of scope (YAGNI)

- Gating CI itself / putting the key in CI (Option B).
- Promoting the judge to an automatic, hands-off gate.
- Changing the rubric, the bar, the dimensions, or the LLM writer.
- Langfuse dashboards; downstream consumption of retrieved chunks (pre-existing deferred).

## Learning-queue flag (candidate)

Concept: "An LLM gate that can disqualify itself." The judge only blocks if it first passes
its own calibration; a judge having a bad day disables the gate rather than failing the
build. Pointer: `judge_gate_decision` + `--judge-gate` in `scripts/run_report_eval.py`.
(Flag in HANDOVER Learning queue on landing, per the one-writer rule — do not write
LEARNING-LOG from here.)
