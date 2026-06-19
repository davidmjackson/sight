# LLM Writer Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LLM writer's prose clear the advisory readability judge on both the exec and programme reports, without inventing any facts, and add a 3-sample median so the noisy judge can be measured reliably.

**Architecture:** Three changes behind the existing `ReportWriter` seam. (1) Four prose directives plus one worked exemplar are added to the LLM writer's prompt so it leads with the first-listed item, gives grounded watch-points, cuts repetition, and matches register. (2) A `sample_judge` helper runs the judge N times and returns the per-dimension median. (3) The eval script's advisory judge pass uses the median and prints the noise range. The deterministic `compose` writer, the section contract, and the judge rubric are untouched.

**Tech Stack:** Python 3.11, pytest, ruff, the standard-library `statistics` module. No new dependencies.

## Global Constraints

- No em dashes in any David-facing doc (use commas, periods, parentheses). Prefer clean prose in code too.
- Section keys are the machine contract: do NOT rename or add keys in `sprintsight/report/audience.py`. They are asserted by the report-quality eval.
- No invented facts. The writer leads with the FIRST-LISTED risk/dependency (already in logged order); it must NOT assert a severity ranking or use "highest", "most severe", or "biggest". Watch-points must be drawn from each item's own wording.
- Do NOT soften the judge rubric. `sprintsight/evals/judge.py` `_SYSTEM` and the `MIN_PER_DIMENSION` / `MIN_MEAN` bars stay exactly as they are.
- Do NOT edit `sprintsight/report/writer.py` (compose). It stays the deterministic CI gate and the LLM writer's fallback.
- Do NOT promote the judge from advisory to a CI gate in this arc.
- The deterministic evals (`scripts/run_watermelon_eval.py`, `scripts/run_report_eval.py` default path) are the CI gate and must stay green offline.
- Run all commands with the venv: `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`.
- This branch (`llm-writer-readability-arc`) is already created off `main`. The design spec is committed at `docs/superpowers/specs/2026-06-19-llm-writer-readability-design.md`.

---

### Task 1: 3-sample median judge helper

**Files:**
- Modify: `sprintsight/evals/judge.py` (add `sample_judge`, add `import statistics`)
- Test: `tests/test_judge.py`

**Interfaces:**
- Consumes: `JudgeFn`, `JudgeScore`, `DIMENSIONS` (already in `judge.py`); `Report` (already imported in the test).
- Produces: `sample_judge(judge: JudgeFn, report: Report, audience: str, n: int = 3) -> JudgeScore`. Each dimension is the low-median of that dimension across the successful samples; the reasons are the last successful sample's reasons. Raises `RuntimeError` if every sample fails.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_judge.py`:

```python
def _sequencing_grader(seq_by_dim: dict[str, list[int]]):
    """Fake grader that returns a different score per call, walking each dimension's list."""
    state = {"i": 0}

    def grade(system, user, schema):
        i = state["i"]
        state["i"] += 1
        return {d: {"score": seq_by_dim[d][i], "reason": f"r{i}-{d}"} for d in seq_by_dim}

    return grade


def test_sample_judge_takes_per_dimension_median():
    from sprintsight.evals.judge import sample_judge

    # clarity samples [2,4,4] -> median 4; every other dim constant at 4.
    seq = {d: [4, 4, 4] for d in DIMENSIONS}
    seq["clarity"] = [2, 4, 4]
    judge = make_judge(grade=_sequencing_grader(seq))
    score = sample_judge(judge, _report(), "exec", n=3)
    assert score.scores["clarity"] == 4
    assert score.scores["audience_fit"] == 4
    assert score.mean == 4.0


def test_sample_judge_single_sample_equals_one_run():
    seq = {d: [3] for d in DIMENSIONS}
    judge = make_judge(grade=_sequencing_grader(seq))
    score = sample_judge(judge, _report(), "exec", n=1)
    assert score.scores == {d: 3 for d in DIMENSIONS}


def test_sample_judge_drops_failed_samples():
    calls = {"i": 0}

    def flaky(system, user, schema):
        calls["i"] += 1
        if calls["i"] == 2:  # second call blows up; it must be dropped, not fatal
            raise RuntimeError("boom")
        return {d: {"score": 4, "reason": "ok"} for d in DIMENSIONS}

    score = sample_judge(make_judge(grade=flaky), _report(), "exec", n=3)
    assert score.scores == {d: 4 for d in DIMENSIONS}


def test_sample_judge_raises_when_all_samples_fail():
    import pytest as _pytest

    def always_fails(system, user, schema):
        raise RuntimeError("boom")

    with _pytest.raises(RuntimeError):
        sample_judge(make_judge(grade=always_fails), _report(), "exec", n=3)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_judge.py -k sample_judge -v`
Expected: FAIL with `ImportError: cannot import name 'sample_judge'`.

- [ ] **Step 3: Implement `sample_judge`**

In `sprintsight/evals/judge.py`, add `import statistics` near the top (with the other imports, after `from typing import Any`). Then add this function just after `make_judge` (after its closing `return judge`):

```python
def sample_judge(judge: JudgeFn, report: Report, audience: str, n: int = 3) -> JudgeScore:
    """Run the judge `n` times and return a JudgeScore of per-dimension low-medians.

    The judge is an LLM and its scores wobble run to run (we saw exec swing 4.2 -> 2.75 with
    no code change). Sampling and taking the median de-noises that without a large budget.
    `median_low` always returns an actually-sampled integer (no 3.5 averages) and leans to the
    stricter side on an even split, which suits a deliberately strict grader. Failed samples are
    dropped; if every sample fails we raise, because there is nothing to report.
    """
    samples: list[JudgeScore] = []
    for _ in range(n):
        try:
            samples.append(judge(report, audience))
        except Exception:  # noqa: BLE001 - advisory path: drop a bad sample, do not abort
            continue
    if not samples:
        raise RuntimeError("all judge samples failed")
    scores = {d: int(statistics.median_low(s.scores.get(d, 0) for s in samples)) for d in DIMENSIONS}
    return JudgeScore(scores=scores, reasons=samples[-1].reasons)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_judge.py -v`
Expected: PASS (the four new tests plus all existing judge tests).

- [ ] **Step 5: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/evals/judge.py tests/test_judge.py`
Expected: no errors.

```bash
git add sprintsight/evals/judge.py tests/test_judge.py
git commit -m "feat(eval): sample_judge takes a per-dimension median to de-noise the LLM judge [SS-7]"
```

---

### Task 2: Prose directives and worked exemplar in the LLM writer prompt

**Files:**
- Modify: `sprintsight/report/llm_writer.py` (`_SYSTEM` constant, `_user_prompt`)
- Test: `tests/test_llm_writer.py`

**Interfaces:**
- Consumes: `Facts`, `PROFILES` (for the test, from `sprintsight.report.audience` and `sprintsight.report.writer`).
- Produces: an enriched `_SYSTEM` string and a `_user_prompt(f: Facts) -> str` that includes the lead-item line. No signature changes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_llm_writer.py`:

```python
def test_system_prompt_carries_the_readability_directives():
    from sprintsight.report.llm_writer import _SYSTEM

    s = _SYSTEM.lower()
    assert "the one to watch" in s            # lead-with-first-item framing
    assert "watch-point" in s                 # grounded watch-point directive
    assert "alignment will be maintained" in s  # the banned-passive marker (in directive + exemplar)
    assert "trajectory and decision" in s     # programme register directive
    # Bright line: never instruct a severity ranking.
    for banned in ("highest", "most severe", "biggest"):
        assert banned in s, f"directive must explicitly forbid '{banned}'"


def test_user_prompt_names_the_lead_item():
    from sprintsight.report.audience import PROFILES
    from sprintsight.report.llm_writer import _user_prompt
    from sprintsight.report.writer import Facts

    f = Facts(
        team="Boreas", audience="exec", profile=PROFILES["exec"],
        burndown_id="b", status_id="s", raid_id="r", metrics=None,
        rag="green", rag_cite="s",
        risks=["First risk.", "Second risk."], deps=[], looking_ahead="",
        claims=[], insufficient=False,
    )
    assert "first risk listed is your lead item" in _user_prompt(f).lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_llm_writer.py -k "directives or lead_item" -v`
Expected: FAIL (today `_SYSTEM` has none of these markers and `_user_prompt` has no lead-item line).

- [ ] **Step 3: Enrich `_SYSTEM`**

In `sprintsight/report/llm_writer.py`, replace the existing `_SYSTEM` (lines 27-31) with:

```python
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
```

- [ ] **Step 4: Add the lead-item line to `_user_prompt`**

In `_user_prompt`, immediately before the final `return "\n".join(lines)`, after the existing `lines.append(f"Write these sections: ...")` line, add:

```python
    lines.append("The first risk listed is your lead item to watch.")
```

- [ ] **Step 5: Run the prompt tests, the writer suite, and the deterministic gate**

Run: `.venv/bin/pytest tests/test_llm_writer.py -v`
Expected: PASS (new prompt tests green; existing fallback/fake-completer tests still green, because the validator and word-cap behaviour are unchanged).

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: exit 0, all cases PASS (compose path is untouched; prompt changes only affect the live LLM path).

- [ ] **Step 6: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/report/llm_writer.py tests/test_llm_writer.py`
Expected: no errors.

```bash
git add sprintsight/report/llm_writer.py tests/test_llm_writer.py
git commit -m "feat(report): LLM writer leads with the one to watch, grounded watch-points, no passive reassurance [SS-7]"
```

---

### Task 3: Wire the eval script's judge pass to the median

**Files:**
- Modify: `scripts/run_report_eval.py` (`_run_judge_pass`, lines 33-52)

**Interfaces:**
- Consumes: `sample_judge` (Task 1), `make_judge`, `build_cases`, `DIMENSIONS` (imported inside `_run_judge_pass`).
- Produces: no new public symbols. The advisory pass now prints a median plus a min-to-max range per dimension. Exit code is still never changed.

This task has no unit test of its own (it is a print-only script path on the key-gated advisory branch). It is verified by reading its output in Task 4. The deterministic gate (the default `compose` path) does not run this branch.

- [ ] **Step 1: Replace the judge-pass body**

In `scripts/run_report_eval.py`, replace the `_run_judge_pass` function (lines 33-52) with exactly this. It collects the `n` raw samples once, reports the median via `sample_judge`, and prints the observed min-to-max range per dimension so the noise is visible:

```python
def _run_judge_pass(writer, n: int = 3) -> None:
    """Advisory LLM-judge readability pass, sampled. Key-gated; never changes the exit code."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key.startswith("sk-ant-") or len(key) < 50:
        print("\n[--judge] skipped: no real ANTHROPIC_API_KEY (advisory, CI-safe).")
        return
    from sprintsight.evals.judge import DIMENSIONS, make_judge, sample_judge
    from sprintsight.evals.report import build_cases

    judge = make_judge()
    print(f"\nReadability (advisory, LLM-judge, median of {n}):")
    for case in build_cases():
        report = writer(case.inputs)
        if report is None or report.insufficient_evidence:
            print(f"  {case.name:16} n/a (insufficient evidence)")
            continue
        audience = case.inputs.get("audience", "programme")
        runs = [judge(report, audience) for _ in range(n)]
        # Feed the already-collected runs to sample_judge so the median logic is shared and the
        # API is not called again. `_q=list(runs)` snapshots the list per call so `runs` stays
        # intact for the range calculation below.
        median = sample_judge(lambda r, a, _q=list(runs): _q.pop(0), report, audience, n=len(runs))
        flag = "PASS" if median.passes else "below-bar"
        cells = []
        for d in DIMENSIONS:
            lo = min(r.scores[d] for r in runs)
            hi = max(r.scores[d] for r in runs)
            span = f"{median.scores[d]}" if lo == hi else f"{median.scores[d]} ({lo}-{hi})"
            cells.append(f"{d}={span}")
        print(f"  {case.name:16} {flag}  mean={median.mean:.2f}  [{', '.join(cells)}]")
```

- [ ] **Step 2: Verify the script still imports and the offline path is unaffected**

Run: `.venv/bin/python scripts/run_report_eval.py --judge`
Expected: exit 0, the report cases PASS, then `[--judge] skipped: no real ANTHROPIC_API_KEY (advisory, CI-safe).` (no key exported in this shell, so the advisory branch is skipped and the gate is unaffected).

- [ ] **Step 3: Lint and commit**

Run: `.venv/bin/ruff check scripts/run_report_eval.py`
Expected: no errors.

```bash
git add scripts/run_report_eval.py
git commit -m "feat(eval): advisory judge pass reports the 3-sample median and noise range [SS-7]"
```

---

### Task 4: Live measurement, verification, and docs

**Files:**
- Modify: `HANDOVER.md`
- Modify: `docs/superpowers/specs/2026-06-19-llm-writer-readability-design.md` (append the live result)

**Interfaces:**
- Consumes: nothing new. This task runs the gates and records the outcome.

- [ ] **Step 1: Confirm the full deterministic gate is green offline**

Run: `.venv/bin/ruff check .`
Expected: no errors.

Run: `.venv/bin/pytest`
Expected: all pass (live judge/calibration tests skip without a key).

Run: `.venv/bin/python scripts/run_watermelon_eval.py`
Expected: exit 0, watermelon 4/4.

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: exit 0, report cases PASS.

- [ ] **Step 2: Run the live sampled judge on the LLM writer and capture the numbers**

This needs the real key. Export it from `.env` (no autoloader), then run the advisory sampled judge on the LLM writer:

Run: `set -a; . ./.env; set +a; .venv/bin/python scripts/run_report_eval.py --llm --judge`
Expected: the Readability block prints, per case, the median and the noise range, e.g. `boreas-exec  PASS  mean=4.00  [clarity=4, audience_fit=4 (3-4), coherence=4, actionability=4]`. Target: boreas-exec and atlas-programme each show every dimension >= 3 and mean >= 3.5. Capture the exact line for each case.

For the contrast, also capture the compose baseline (compose stays the fallback, so this shows the LLM lift):

Run: `set -a; . ./.env; set +a; .venv/bin/python scripts/run_report_eval.py --judge`
Expected: the compose median lines (expected to remain below bar, the known deterministic ceiling). Capture them.

**Honesty clause:** if a dimension stays below 3 for a reason that cannot be fixed without inventing a fact, owner, date, or ranking, STOP and report it to David. Do not reword purely to lift the score, and do not touch the judge rubric.

- [ ] **Step 3: Append the live result to the design spec**

Add a short "Result (2026-06-19)" section to `docs/superpowers/specs/2026-06-19-llm-writer-readability-design.md` with the before and after median numbers for boreas-exec and atlas-programme (before: exec 2.75 / programme 3.00 single-sample; after: the captured medians), and the compose baseline for contrast.

- [ ] **Step 4: Update HANDOVER.md**

Replace the "NEXT ARC" note in the writer-readability section with the outcome: the LLM-writer-readability arc is complete on branch `llm-writer-readability-arc`; the writer now leads with the one to watch, gives grounded watch-points, and matches register; `sample_judge` added so the advisory judge is read as a 3-sample median; deterministic gate unchanged and green; live judge median moved from <before> to <captured after>. Note the judge stays advisory (promotion still deferred) and record the next candidate decision (promote the judge to a gate, or not).

- [ ] **Step 5: Append one line to the HANDOVER `Learning queue`**

Per CLAUDE.md, do NOT edit `LEARNING-LOG.md`. Append one line to the `Learning queue` section of `HANDOVER.md` (format: concept | one line on what is new | code/stage pointer | date):

```
- De-noising an LLM judge with a median | a single LLM-judge run wobbles run to run, so we sample it 3x and take the median; a noisy judge cannot be a gate yet | sprintsight/evals/judge.py sample_judge + scripts/run_report_eval.py | 2026-06-19
```

- [ ] **Step 6: Commit**

```bash
git add HANDOVER.md docs/superpowers/specs/2026-06-19-llm-writer-readability-design.md
git commit -m "docs: record LLM-writer-readability arc result; flag judge-median concept to learning queue [SS-7]"
```

---

## Notes for the executor

- Jira: this arc is a new SS-7 child Story. Create it and move it To Do -> In Progress at the start, In Progress -> In Review when code is done, and In Review -> Done only after Task 4's gates pass and docs are updated. Drive the board via the Composio MCP; never set Done on create; post a completion comment when marking Done. (See CLAUDE.md and the Jira memories.)
- This branch (`llm-writer-readability-arc`) is already created off `main`; the design spec is already committed on it.
- Do not promote the judge from advisory to a CI gate in this arc, and do not change the judge rubric.
- Do not edit `sprintsight/report/writer.py` (compose); it stays the gate and fallback.
