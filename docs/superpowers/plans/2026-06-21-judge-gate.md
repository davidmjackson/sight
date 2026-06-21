# Judge Gate (live check) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the LLM-as-judge readability pass fail a deliberate, key-holding pre-merge run via a new `--judge-gate` flag, guarded by calibration and a 5-sample median, without touching CI.

**Architecture:** A pure decision function in `judge.py` turns per-case median scores plus a calibration-trust boolean into a block/allow verdict. `scripts/run_report_eval.py` gains a `--judge-gate` flag that scores the eval reports 5x, runs the calibration meta-eval first, and folds the verdict into the process exit code. The existing advisory `--judge` flag and the offline CI invocation are unchanged.

**Tech Stack:** Python 3.11, pytest, existing `sprintsight.evals.judge` / `sprintsight.evals.calibration` / `sprintsight.evals.report` modules. No new dependencies.

## Global Constraints

- No new third-party dependencies.
- CI stays fully offline: no code path reachable without `--judge-gate` may call the Anthropic API. All tests use injected fake graders; none call the API.
- The real-key guard pattern is fixed: a key is valid iff it `startswith("sk-ant-")` AND `len >= 50`. Reuse verbatim.
- The readability bar is unchanged and lives in `judge.py`: `MIN_PER_DIMENSION = 3`, `MIN_MEAN = 3.5`, `DIMENSIONS = ("clarity", "audience_fit", "coherence", "actionability")`. Do NOT edit the rubric or bar.
- No em dashes in any human-facing copy (commas/periods/parentheses).
- Gate path samples n=5; advisory path stays n=3.
- Two safety rules are absolute: (1) if calibration fails, the gate does NOT block; (2) a report that could not be scored (insufficient evidence, or every judge sample errored) does NOT block.

---

### Task 1: Pure gate-decision function in judge.py

**Files:**
- Modify: `sprintsight/evals/judge.py`
- Test: `tests/test_judge.py`

**Interfaces:**
- Consumes: existing `JudgeScore` (frozen dataclass; `.scores: dict[str,int]`, `.mean: float`, `.passes: bool`).
- Produces:
  - `GateDecision` frozen dataclass: `blocks: bool`, `reasons: list[str]`.
  - `judge_gate_decision(medians: list[tuple[str, JudgeScore | None]], calibration_ok: bool) -> GateDecision`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_judge.py`:

```python
from sprintsight.evals.judge import GateDecision, judge_gate_decision, make_judge, DIMENSIONS


def _score(values: dict[str, int]):
    """Build a real JudgeScore via the fake grader so .passes uses the real bar."""
    grade = lambda system, user, schema: {d: {"score": values[d], "reason": "x"} for d in values}
    return make_judge(grade=grade)(_report(), "exec")


def test_gate_allows_when_all_pass_and_calibration_ok():
    good = _score({d: 4 for d in DIMENSIONS})  # mean 4.0, every dim >= 3 -> passes
    decision = judge_gate_decision([("boreas-exec", good)], calibration_ok=True)
    assert isinstance(decision, GateDecision)
    assert decision.blocks is False


def test_gate_blocks_when_a_report_is_below_bar_and_calibration_ok():
    bad = _score({**{d: 4 for d in DIMENSIONS}, "coherence": 2})  # one dim < 3 -> fails bar
    decision = judge_gate_decision([("atlas-programme", bad)], calibration_ok=True)
    assert decision.blocks is True
    assert any("atlas-programme" in r for r in decision.reasons)


def test_gate_does_not_block_when_calibration_fails_even_if_below_bar():
    bad = _score({**{d: 4 for d in DIMENSIONS}, "coherence": 2})
    decision = judge_gate_decision([("atlas-programme", bad)], calibration_ok=False)
    assert decision.blocks is False
    assert any("calibration" in r.lower() for r in decision.reasons)


def test_gate_does_not_block_on_unscored_report():
    good = _score({d: 4 for d in DIMENSIONS})
    decision = judge_gate_decision(
        [("echo-thin", None), ("boreas-exec", good)], calibration_ok=True
    )
    assert decision.blocks is False


def test_gate_still_blocks_on_real_failure_alongside_an_unscored_report():
    bad = _score({**{d: 4 for d in DIMENSIONS}, "coherence": 2})
    decision = judge_gate_decision(
        [("echo-thin", None), ("atlas-programme", bad)], calibration_ok=True
    )
    assert decision.blocks is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_judge.py -k gate -v`
Expected: FAIL with `ImportError: cannot import name 'GateDecision'` (and `judge_gate_decision`).

- [ ] **Step 3: Implement the decision function**

In `sprintsight/evals/judge.py`, after the `JudgeScore` class, add:

```python
@dataclass(frozen=True)
class GateDecision:
    """Verdict from the readability gate: whether to block, plus human-readable reasons."""

    blocks: bool
    reasons: list[str]


def judge_gate_decision(
    medians: list[tuple[str, "JudgeScore | None"]],
    calibration_ok: bool,
) -> GateDecision:
    """Decide whether the readability judge should fail the run.

    Two absolute safety rules: a judge that failed its calibration does not block, and a
    report that could not be scored (None) does not block. Otherwise the gate blocks on any
    scored report whose median is below the readability bar.
    """
    reasons: list[str] = []
    if not calibration_ok:
        reasons.append(
            "calibration failed: judge not trusted this run, advisory only (not blocking)."
        )
        return GateDecision(blocks=False, reasons=reasons)

    below: list[str] = []
    for name, score in medians:
        if score is None:
            reasons.append(f"{name}: not scored (insufficient evidence or all samples failed); not blocking.")
            continue
        if score.passes:
            reasons.append(f"{name}: passes (mean={score.mean:.2f}).")
        else:
            below.append(name)
            reasons.append(f"{name}: below bar (scores={score.scores}, mean={score.mean:.2f}).")

    if below:
        reasons.append(f"GATE BLOCKS: {', '.join(below)} below the readability bar.")
        return GateDecision(blocks=True, reasons=reasons)
    reasons.append("GATE OK: all scored reports clear the readability bar.")
    return GateDecision(blocks=False, reasons=reasons)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_judge.py -k gate -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full judge test file + ruff to confirm no regressions**

Run: `.venv/bin/python -m pytest tests/test_judge.py -q && .venv/bin/ruff check sprintsight/evals/judge.py tests/test_judge.py`
Expected: all pass, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/evals/judge.py tests/test_judge.py
git commit -m "feat(eval): pure judge_gate_decision (calibration-guarded, unscored never blocks) [SS-7]"
```

---

### Task 2: Extract the shared per-case scorer in the eval script

**Files:**
- Modify: `scripts/run_report_eval.py`
- Test: `tests/test_judge_runner.py`

**Interfaces:**
- Consumes: existing `sample_judge` (for the shared median logic), `JudgeFn`.
- Produces: `_score_one(judge, report, audience, n) -> tuple[JudgeScore | None, list[JudgeScore]]` — runs the judge `n` times, drops failed samples, returns the per-dimension median (None if every sample failed) and the surviving raw runs (for lo/hi span printing). `_run_judge_pass` is rewired to call it; its external behaviour (advisory, never changes exit code, skips without key) is unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_judge_runner.py`:

```python
def test_score_one_returns_median_and_runs():
    from sprintsight.evals.judge import DIMENSIONS, make_judge
    from sprintsight.report.contract import Report

    mod = _load_runner()
    report = Report(team="Boreas", audience="exec", sections={"overall RAG": "Green."})
    # clarity walks [2,4,4] -> median 4; all other dims constant 4.
    state = {"i": 0}

    def grade(system, user, schema):
        i = state["i"]; state["i"] += 1
        clar = [2, 4, 4][i]
        return {d: {"score": (clar if d == "clarity" else 4), "reason": "x"} for d in DIMENSIONS}

    median, runs = mod._score_one(make_judge(grade=grade), report, "exec", n=3)
    assert median is not None
    assert median.scores["clarity"] == 4
    assert len(runs) == 3


def test_score_one_returns_none_when_all_samples_fail():
    from sprintsight.report.contract import Report

    mod = _load_runner()
    report = Report(team="Boreas", audience="exec", sections={"overall RAG": "Green."})

    def boom(report, audience):
        raise RuntimeError("api down")

    median, runs = mod._score_one(boom, report, "exec", n=3)
    assert median is None
    assert runs == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_judge_runner.py -k score_one -v`
Expected: FAIL with `AttributeError: module 'run_report_eval' has no attribute '_score_one'`.

- [ ] **Step 3: Add `_score_one` and rewire `_run_judge_pass`**

In `scripts/run_report_eval.py`, add this helper above `_run_judge_pass`:

```python
def _score_one(judge, report, audience, n):
    """Score one report `n` times; return (median JudgeScore | None, surviving runs).

    Shared by the advisory pass (n=3) and the gate (n=5). Failed samples are dropped; if every
    sample fails the median is None. Reuses sample_judge's median logic by feeding it the already
    collected runs (the `_q=list(runs)` snapshot leaves `runs` intact for span printing).
    """
    from sprintsight.evals.judge import sample_judge

    runs = []
    for _ in range(n):
        try:
            runs.append(judge(report, audience))
        except Exception:  # noqa: BLE001 - advisory/gate path: drop a bad sample, keep going
            continue
    if not runs:
        return None, []
    median = sample_judge(lambda r, a, _q=list(runs): _q.pop(0), report, audience, n=len(runs))
    return median, runs
```

Then replace the body of `_run_judge_pass` (keep its signature `def _run_judge_pass(writer, n: int = 3) -> None:` and the leading key-skip check) so the per-case work calls `_score_one`:

```python
def _run_judge_pass(writer, n: int = 3) -> None:
    """Advisory LLM-judge readability pass, sampled. Key-gated; never changes the exit code."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key.startswith("sk-ant-") or len(key) < 50:
        print("\n[--judge] skipped: no real ANTHROPIC_API_KEY (advisory, CI-safe).")
        return
    from sprintsight.evals.judge import DIMENSIONS, make_judge
    from sprintsight.evals.report import build_cases

    judge = make_judge()
    print(f"\nReadability (advisory, LLM-judge, median of {n}):")
    for case in build_cases():
        report = writer(case.inputs)
        if report is None or report.insufficient_evidence:
            print(f"  {case.name:16} n/a (insufficient evidence)")
            continue
        audience = case.inputs.get("audience", "programme")
        median, runs = _score_one(judge, report, audience, n)
        if median is None:
            print(f"  {case.name:16} n/a (all judge samples failed)")
            continue
        flag = "PASS" if median.passes else "below-bar"
        cells = []
        for d in DIMENSIONS:
            lo = min(r.scores[d] for r in runs)
            hi = max(r.scores[d] for r in runs)
            span = f"{median.scores[d]}" if lo == hi else f"{median.scores[d]} ({lo}-{hi})"
            cells.append(f"{d}={span}")
        print(f"  {case.name:16} {flag}  mean={median.mean:.2f}  [{', '.join(cells)}]")
```

(This drops the previous per-sample "dropped a judge sample" diagnostic line; the lo/hi span already conveys variance and an all-failed case still prints n/a. No test asserts that line.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_judge_runner.py -k score_one -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the whole runner test file to confirm the advisory path still works**

Run: `.venv/bin/python -m pytest tests/test_judge_runner.py -q`
Expected: all pass (existing skip-without-key and exception-path tests still green).

- [ ] **Step 6: Commit**

```bash
git add scripts/run_report_eval.py tests/test_judge_runner.py
git commit -m "refactor(eval): extract shared _score_one for the judge passes [SS-7]"
```

---

### Task 3: Wire the `--judge-gate` flag and fold it into the exit code

**Files:**
- Modify: `scripts/run_report_eval.py`
- Test: `tests/test_judge_runner.py`

**Interfaces:**
- Consumes: `_score_one` (Task 2), `judge_gate_decision` (Task 1), `run_calibration` (existing, returns a `SuiteReport` with `.pass_rate: float`), `make_judge`, `build_cases`.
- Produces:
  - `_run_judge_gate(writer, n=5, judge=None, run_calib=None) -> bool` — returns True iff the gate should block. `judge` and `run_calib` are injectable for offline tests (default to `make_judge()` and `run_calibration`).
  - `main()` honours `--judge-gate`: requires a real key (else returns 2), runs the gate, and returns non-zero if the deterministic eval fails OR the gate blocks.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_judge_runner.py`:

```python
import types as _types


def _gate_fakes(score_values):
    """Return (writer, judge, run_calib_factory) wired with a fake grader at score_values."""
    from sprintsight.evals.judge import DIMENSIONS, make_judge
    from sprintsight.report.contract import Report

    def writer(inputs):
        return Report(team="T", audience="exec", sections={"overall RAG": "Green."})

    def grade(system, user, schema):
        return {d: {"score": score_values[d], "reason": "x"} for d in DIMENSIONS}

    judge = make_judge(grade=grade)
    return writer, judge


def test_run_judge_gate_blocks_below_bar_when_calibration_ok():
    from sprintsight.evals.judge import DIMENSIONS

    mod = _load_runner()
    below = {**{d: 4 for d in DIMENSIONS}, "coherence": 2}
    writer, judge = _gate_fakes(below)
    blocks = mod._run_judge_gate(
        writer, n=3, judge=judge, run_calib=lambda j: _types.SimpleNamespace(pass_rate=1.0)
    )
    assert blocks is True


def test_run_judge_gate_does_not_block_when_calibration_fails():
    from sprintsight.evals.judge import DIMENSIONS

    mod = _load_runner()
    below = {**{d: 4 for d in DIMENSIONS}, "coherence": 2}
    writer, judge = _gate_fakes(below)
    blocks = mod._run_judge_gate(
        writer, n=3, judge=judge, run_calib=lambda j: _types.SimpleNamespace(pass_rate=0.5)
    )
    assert blocks is False


def test_run_judge_gate_allows_passing_reports():
    from sprintsight.evals.judge import DIMENSIONS

    mod = _load_runner()
    good = {d: 4 for d in DIMENSIONS}
    writer, judge = _gate_fakes(good)
    blocks = mod._run_judge_gate(
        writer, n=3, judge=judge, run_calib=lambda j: _types.SimpleNamespace(pass_rate=1.0)
    )
    assert blocks is False


def test_main_judge_gate_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_report_eval.py", "--judge-gate"])
    mod = _load_runner()
    assert mod.main() == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_judge_runner.py -k "gate or judge_gate" -v`
Expected: FAIL with `AttributeError: ... has no attribute '_run_judge_gate'` (and the key test failing because main does not yet handle the flag).

- [ ] **Step 3: Implement `_run_judge_gate`**

In `scripts/run_report_eval.py`, add below `_run_judge_pass`:

```python
def _run_judge_gate(writer, n: int = 5, judge=None, run_calib=None) -> bool:
    """Blocking readability gate (live, key-holding runs only). Returns True iff it should block.

    Runs the calibration meta-eval first; only a trusted judge is allowed to block. Scores each
    eval report `n` times and takes the median. `judge`/`run_calib` are injectable for offline
    tests; they default to the real (key-gated) judge and calibration.
    """
    from sprintsight.evals.calibration import run_calibration
    from sprintsight.evals.judge import judge_gate_decision, make_judge
    from sprintsight.evals.report import build_cases

    judge = judge or make_judge()
    run_calib = run_calib or run_calibration
    calibration_ok = run_calib(judge).pass_rate == 1.0

    medians: list[tuple[str, object]] = []
    print(f"\nReadability GATE (LLM-judge, median of {n}, calibration_ok={calibration_ok}):")
    for case in build_cases():
        report = writer(case.inputs)
        if report is None or report.insufficient_evidence:
            medians.append((case.name, None))
            print(f"  {case.name:16} n/a (insufficient evidence)")
            continue
        audience = case.inputs.get("audience", "programme")
        median, _runs = _score_one(judge, report, audience, n)
        medians.append((case.name, median))
        if median is None:
            print(f"  {case.name:16} n/a (all judge samples failed)")
        else:
            flag = "PASS" if median.passes else "below-bar"
            print(f"  {case.name:16} {flag}  mean={median.mean:.2f}")

    decision = judge_gate_decision(medians, calibration_ok)
    for line in decision.reasons:
        print(f"    {line}")
    print(f"\nJUDGE GATE: {'BLOCKS' if decision.blocks else 'OK'}")
    return decision.blocks
```

- [ ] **Step 4: Wire `--judge-gate` into `main` and fold the exit code**

In `scripts/run_report_eval.py`, replace the tail of `main()` (from the `if "--judge" in sys.argv:` block through `return ...`) with:

```python
    if "--judge" in sys.argv:
        try:
            _run_judge_pass(writer)
        except Exception as exc:  # noqa: BLE001 - advisory pass must never change the exit code
            print(f"\n[--judge] error (advisory, ignored): {exc}")

    gate_blocks = False
    if "--judge-gate" in sys.argv:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key.startswith("sk-ant-") or len(key) < 50:
            print("ERROR: --judge-gate needs a real ANTHROPIC_API_KEY in the environment.")
            return 2
        try:
            gate_blocks = _run_judge_gate(writer)
        except Exception as exc:  # noqa: BLE001 - infra failure must not turn the build red
            print(f"\n[--judge-gate] error (infra; advisory, not blocking): {exc}")
            gate_blocks = False

    return 1 if (report.pass_rate != 1.0 or gate_blocks) else 0
```

Also update the module docstring usage block to document the new flag (add a line):

```
    .venv/bin/python scripts/run_report_eval.py --llm --judge-gate  # live: gate on readability
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_judge_runner.py -k "gate or judge_gate" -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Run the full suite + ruff**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check scripts/run_report_eval.py sprintsight/evals/judge.py tests/`
Expected: all pass (was 89 passed/3 skipped; now higher), ruff clean.

- [ ] **Step 7: Confirm the deterministic gate and CI path are untouched**

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: deterministic report eval prints, exit code 0 (no judge output, no API call).

Run: `.venv/bin/python -m pytest tests/test_report_eval.py tests/test_calibration.py -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add scripts/run_report_eval.py tests/test_judge_runner.py
git commit -m "feat(eval): --judge-gate fails a live run on below-bar readability (calibration + 5-sample median) [SS-7]"
```

---

## Post-implementation (not a code task)

- Append one line to the HANDOVER `Learning queue` (the spec's candidate concept: "an LLM gate that can disqualify itself" via calibration). Do NOT edit LEARNING-LOG.md from here.
- Live verification (requires the real key, run by hand): `.venv/bin/python scripts/run_report_eval.py --llm --judge-gate` and record the verdict in HANDOVER. This is operator-run, not part of CI.

## Self-Review notes

- Spec coverage: new `--judge-gate` flag (Task 3), `--judge` unchanged (Task 2 preserves behaviour), CI untouched (Task 3 main returns deterministic exit when flag absent; Step 7 verifies), pure decision function + offline tests (Task 1), calibration precondition + 5-sample median (Task 3 default n=5; calibration in `_run_judge_gate`), both safety rules (Task 1 tests), key guard (Task 3 main test). All covered.
- Type consistency: `judge_gate_decision(medians, calibration_ok) -> GateDecision` used identically in Task 1 and Task 3; `_score_one(...) -> (JudgeScore | None, list)` defined Task 2, consumed Task 3; `run_calib(judge).pass_rate` matches `SuiteReport.pass_rate` (confirmed present, harness.py:67).
- No placeholders: every step has runnable code/commands and expected output.
