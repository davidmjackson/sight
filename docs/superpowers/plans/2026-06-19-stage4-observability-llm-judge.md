# Stage 4 Observability + LLM-as-Judge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an advisory LLM-as-judge readability eval (with a calibration meta-eval that grades the judge) and per-node graph tracing, without changing the offline/deterministic CI gate.

**Architecture:** A new `judge.py` scores a finished Report on four prose dimensions via an injected grader (fake in tests, real Anthropic on the key-gated path), mirroring the existing `llm_writer.py` seam. A `calibration.py` meta-eval reuses the generic harness to assert the judge ranks hand-labelled good/bad anchor reports correctly. The graph builder gains an optional tracer that wraps each node in a span, reusing the existing `Tracer` protocol so the default path stays no-op and CI never calls the API.

**Tech Stack:** Python 3.11+, Anthropic SDK (tool-use structured output), the in-repo deterministic eval harness, LangGraph, the existing `tracing.py` Langfuse adapter.

## Global Constraints

- Python `>=3.11`; deps limited to existing: `anthropic>=0.40`, `langgraph>=0.2`, `langfuse>=4` (optional `eval` extra). Do NOT add new dependencies.
- Default path is OFFLINE and DETERMINISTIC. CI never calls the API. Any real LLM call is key-gated: require `ANTHROPIC_API_KEY` starting `sk-ant-` and length `>= 50`, else skip/exit 2.
- The judge is ADVISORY this stage: it never changes a suite's pass/fail or any CI exit code.
- The judge scores prose ONLY (clarity, audience_fit, coherence, actionability). It must NOT re-check citations, grounding, word caps, or section presence.
- Lint clean under `ruff` (line-length 100, rules E/F/I/UP/B). No em dashes in any doc a human reads (use commas, periods, parentheses).
- Anthropic structured output via tool-use with `tool_choice` forcing the tool, mirroring `sprintsight/report/llm_writer.py:_anthropic_completer`. Lazy-import `anthropic` inside the call only.
- Model: `claude-sonnet-4-6` (same family as the writer; the judge uses its own separate prompt/role).
- Run tests with `.venv/bin/python -m pytest`; run eval scripts with `.venv/bin/python scripts/<name>.py`.

---

## File Structure

- Create `sprintsight/evals/judge.py` — the readability judge: `JudgeScore`, `make_judge`, rubric prompt, schema, advisory pass-bar, real Anthropic grader. Knows nothing about Langfuse or the graph.
- Create `sprintsight/evals/calibration.py` — anchor reports + `run_calibration(judge)` meta-eval. Depends on the judge and the harness only.
- Modify `sprintsight/graph/builder.py` — add an optional `tracer` to `build_graph`/`run`; wrap each node in a span.
- Modify `scripts/run_report_eval.py` — add an opt-in, key-gated, advisory `--judge` pass.
- Create `scripts/run_calibration.py` — live, key-gated runner that grades the judge against the anchors.
- Create tests: `tests/test_judge.py`, `tests/test_calibration.py`, `tests/test_graph_tracing.py`.
- Create `docs/evals/readability-judge-eval.md` (house style), `docs/adr/ADR-0003-graph-tracing.md`.
- Modify `HANDOVER.md`, `LEARNING-LOG.md`.

---

## Task 1: Readability judge (judge.py)

**Files:**
- Create: `sprintsight/evals/judge.py`
- Test: `tests/test_judge.py`
- Create: `docs/evals/readability-judge-eval.md`

**Interfaces:**
- Consumes: `sprintsight.report.contract.Report` (fields: `team: str`, `audience: str`, `sections: dict[str,str]`, `claims: list[Claim]`, `insufficient_evidence: bool`).
- Produces:
  - `DIMENSIONS = ("clarity", "audience_fit", "coherence", "actionability")`
  - `Grader = Callable[[str, str, dict[str, Any]], dict[str, Any]]` (system, user, schema) -> raw dict.
  - `JudgeFn = Callable[[Report, str], JudgeScore]` (report, audience) -> score.
  - `JudgeScore` dataclass: `scores: dict[str,int]`, `reasons: dict[str,str]`, `.mean: float`, `.passes: bool`.
  - `make_judge(grade: Grader | None = None, model: str = DEFAULT_MODEL) -> JudgeFn`
  - `_anthropic_grader(model: str) -> Grader`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_judge.py
import os

import pytest

from sprintsight.evals.judge import DIMENSIONS, JudgeScore, _anthropic_grader, make_judge
from sprintsight.report.contract import Report


def _report(audience: str = "exec") -> Report:
    return Report(
        team="Boreas",
        audience=audience,
        sections={"overall RAG": "On track and green.", "ask/decision needed": "Approve one reviewer."},
    )


def _fake_grader(scores: dict[str, int]):
    def grade(system, user, schema):
        return {d: {"score": scores[d], "reason": f"r-{d}"} for d in scores}
    return grade


def test_judge_returns_structured_scores_and_reasons():
    judge = make_judge(grade=_fake_grader({d: 5 for d in DIMENSIONS}))
    score = judge(_report(), "exec")
    assert score.scores == {d: 5 for d in DIMENSIONS}
    assert set(score.reasons) == set(DIMENSIONS)
    assert score.mean == 5.0
    assert score.passes is True


def test_judge_fails_bar_when_one_dimension_low():
    bad = {d: 5 for d in DIMENSIONS}
    bad["clarity"] = 2
    score = make_judge(grade=_fake_grader(bad))(_report(), "exec")
    assert score.passes is False


def test_judge_fails_bar_when_mean_below_four_even_if_each_at_least_three():
    score = make_judge(grade=_fake_grader({d: 3 for d in DIMENSIONS}))(_report(), "exec")
    # every dimension == 3 (>= MIN_PER_DIMENSION) but mean 3.0 < MIN_MEAN 4.0
    assert score.passes is False


def test_judge_handles_missing_dimension_as_failing():
    def partial_grader(system, user, schema):
        return {"clarity": {"score": 5, "reason": "ok"}}  # other three missing
    score = make_judge(grade=partial_grader)(_report(), "exec")
    assert score.scores["audience_fit"] == 0
    assert score.passes is False


def test_anthropic_grader_constructs_without_calling_api():
    assert callable(_anthropic_grader("claude-sonnet-4-6"))


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-")
    or len(os.getenv("ANTHROPIC_API_KEY", "")) < 50,
    reason="no real Anthropic key wired",
)
def test_live_judge_scores_a_clean_report_highly():
    score = make_judge()(_report(), "exec")
    assert score.mean >= 3.0, score.scores
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_judge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.evals.judge'`

- [ ] **Step 3: Write the judge module**

```python
# sprintsight/evals/judge.py
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

DEFAULT_MODEL = "claude-sonnet-4-6"  # same family as the writer; judge has its own prompt/role

DIMENSIONS = ("clarity", "audience_fit", "coherence", "actionability")

# Advisory pass bar (spec section 3.3): every dimension >= 3 AND mean >= 4. Tunable pre-gate.
MIN_PER_DIMENSION = 3
MIN_MEAN = 4.0

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
    "actionability (the ask or decision-needed is specific; the reader knows what to do next). "
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
    body = "\n\n".join(f"## {k}\n{v}" for k, v in report.sections.items())
    return f"Audience: {audience}.\nReport for team {report.team}:\n\n{body or '(no sections)'}"


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_judge.py -v`
Expected: PASS (the live test is SKIPPED without a key)

- [ ] **Step 5: Write the judge eval spec doc**

Create `docs/evals/readability-judge-eval.md` documenting: purpose (prose qualities only), the four-dimension rubric, the 1-to-5 scale, the advisory pass bar (every dimension >= 3 and mean >= 4), that it is key-gated and advisory until calibration passes, and a pointer to `calibration.py` as the meta-eval that grades it. Match the plain-English, no-em-dash house style of `docs/evals/watermelon-eval.md`. Keep to roughly one page.

- [ ] **Step 6: Run ruff and commit**

```bash
.venv/bin/ruff check sprintsight/evals/judge.py tests/test_judge.py
git add sprintsight/evals/judge.py tests/test_judge.py docs/evals/readability-judge-eval.md
git commit -m "feat(eval): LLM-as-judge readability scorer (advisory, key-gated) [SS-7]"
```

---

## Task 2: Calibration meta-eval (calibration.py)

**Files:**
- Create: `sprintsight/evals/calibration.py`
- Test: `tests/test_calibration.py`

**Interfaces:**
- Consumes: `JudgeFn`, `JudgeScore`, `DIMENSIONS` from `sprintsight.evals.judge`; `Report` from contract; `Assertion`, `Case`, `SuiteReport`, `run_suite` from `sprintsight.evals.harness`.
- Produces:
  - `Anchor` dataclass: `name: str`, `report: Report`, `audience: str`, `should_pass: bool`.
  - `anchors() -> list[Anchor]`
  - `run_calibration(judge: JudgeFn) -> SuiteReport`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_calibration.py
import os

import pytest

from sprintsight.evals.calibration import anchors, run_calibration
from sprintsight.evals.judge import DIMENSIONS, JudgeScore


def _score(value: int) -> JudgeScore:
    return JudgeScore(scores={d: value for d in DIMENSIONS}, reasons={d: "" for d in DIMENSIONS})


def test_anchors_include_both_good_and_bad():
    labels = {a.should_pass for a in anchors()}
    assert labels == {True, False}, "calibration needs at least one good and one bad anchor"


def test_calibration_green_when_judge_agrees_with_labels():
    # Oracle judge: look up each anchor's known truth by report identity (run_calibration
    # passes the same Report object straight through to the judge).
    truth = {id(a.report): a.should_pass for a in anchors()}

    def oracle(report, audience):
        return _score(5) if truth[id(report)] else _score(1)

    report = run_calibration(oracle)
    assert report.pass_rate == 1.0, report.summary()


def test_calibration_fails_when_judge_cannot_separate_good_from_bad():
    # A blind judge that passes everything must fail calibration on the bad anchors.
    def blind(report, audience):
        return _score(5)

    report = run_calibration(blind)
    assert report.pass_rate < 1.0


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-")
    or len(os.getenv("ANTHROPIC_API_KEY", "")) < 50,
    reason="no real Anthropic key wired",
)
def test_live_judge_passes_calibration():
    from sprintsight.evals.judge import make_judge
    report = run_calibration(make_judge())
    assert report.pass_rate == 1.0, report.summary()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_calibration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.evals.calibration'`

- [ ] **Step 3: Write the calibration module**

```python
# sprintsight/evals/calibration.py
"""Calibration meta-eval: grade the judge before trusting it (Stage 4, SS-7, spec section 4).

A small set of hand-labelled anchor reports. We assert the judge scores the clearly-good
anchors as passing and the clearly-bad anchors as below-bar. If the judge cannot separate
obvious good from obvious bad, it is not trustworthy and must not gate. Same pattern as every
eval: known truth, scored. Anchors are hand-authored fixtures, independent of the live writer,
so the calibration is stable across writer changes.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sprintsight.evals.harness import Assertion, Case, SuiteReport, run_suite
from sprintsight.evals.judge import JudgeFn, JudgeScore
from sprintsight.report.contract import Report

_GOOD_EXEC = Report(
    team="Boreas",
    audience="exec",
    sections={
        "overall RAG": "Green. Sprint 15 delivered on plan and the release date holds.",
        "top 3 risks": "One vendor dependency is slipping. Two minor risks are contained.",
        "ask/decision needed": "Approve one extra reviewer for two weeks to protect the date.",
    },
)

_WAFFLY_EXEC = Report(
    team="Boreas",
    audience="exec",
    sections={
        "overall RAG": (
            "At this moment in time it could broadly be said that, on balance and all things "
            "considered, the overall directional posture of the workstream remains in a state "
            "that is arguably not inconsistent with a generally positive trajectory, subject to "
            "the usual caveats and the evolving nature of the broader delivery landscape."
        ),
        "top 3 risks": "Various items of a risk-shaped nature may or may not require attention.",
        "ask/decision needed": "Continue to monitor and revisit as appropriate in due course.",
    },
)

_JARGON_EXEC = Report(
    team="Atlas",
    audience="exec",
    sections={
        "overall RAG": "Amber: WIP over the cap, burndown flat, carry-over spiking on the s15 board.",
        "top 3 risks": "Blocked tickets in the sprint backlog; velocity dipped below the rolling mean.",
        "ask/decision needed": "Re-baseline the story-point commitment for the next iteration.",
    },
)

_VAGUE_ASK_EXEC = Report(
    team="Boreas",
    audience="exec",
    sections={
        "overall RAG": "Green and on track.",
        "top 3 risks": "A dependency risk and a couple of smaller risks.",
        "ask/decision needed": "Some support from leadership would be helpful at some point.",
    },
)


@dataclass(frozen=True)
class Anchor:
    """One calibration anchor: a report plus the known truth about its prose quality."""

    name: str
    report: Report
    audience: str
    should_pass: bool  # the hand-assigned truth: is this report's prose acceptable?


def anchors() -> list[Anchor]:
    """Hand-labelled good/bad reports the judge must rank correctly to be trusted."""
    return [
        Anchor("good-exec", _GOOD_EXEC, "exec", True),
        Anchor("waffly-exec", _WAFFLY_EXEC, "exec", False),
        Anchor("jargon-exec", _JARGON_EXEC, "exec", False),
        Anchor("vague-ask-exec", _VAGUE_ASK_EXEC, "exec", False),
    ]


def _expectation(anchor: Anchor) -> Callable[[JudgeScore], Assertion]:
    def check(score: JudgeScore) -> Assertion:
        ok = score.passes == anchor.should_pass
        return Assertion(
            "calibration",
            ok,
            f"{anchor.name}: judge passes={score.passes}, expected {anchor.should_pass} "
            f"(scores={score.scores})",
        )

    return check


def run_calibration(judge: JudgeFn) -> SuiteReport:
    """Run every anchor through `judge` and assert it matches the anchor's known truth."""
    cases = [
        Case(name=a.name, inputs=a, assertions=[_expectation(a)]) for a in anchors()
    ]

    def subject(anchor: Anchor) -> JudgeScore:
        return judge(anchor.report, anchor.audience)

    return run_suite(cases, subject)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_calibration.py -v`
Expected: PASS (live test SKIPPED without a key)

- [ ] **Step 5: Run ruff and commit**

```bash
.venv/bin/ruff check sprintsight/evals/calibration.py tests/test_calibration.py
git add sprintsight/evals/calibration.py tests/test_calibration.py
git commit -m "feat(eval): calibration meta-eval that grades the readability judge [SS-7]"
```

---

## Task 3: Per-node graph tracing

**Files:**
- Modify: `sprintsight/graph/builder.py`
- Test: `tests/test_graph_tracing.py`
- Create: `docs/adr/ADR-0003-graph-tracing.md`

**Interfaces:**
- Consumes: `Tracer`, `NoOpTracer`, `get_tracer` from `sprintsight.evals.tracing`.
- Produces: `build_graph(..., tracer: Tracer | None = None)` and `run(..., tracer: Tracer | None = None)` emit one `graph:run` span containing `node:retrieval`, `node:risk`, `node:report_writer` spans. Default tracer is no-op (CI unchanged).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_tracing.py
from contextlib import contextmanager

from sprintsight.evals.fixtures import artifacts_for
from sprintsight.graph.builder import run


class RecordingTracer:
    """Captures span names in order. Stand-in for the Langfuse tracer in tests."""

    def __init__(self) -> None:
        self.spans: list[str] = []

    @contextmanager
    def span(self, name: str):
        self.spans.append(name)
        yield None

    def flush(self) -> None:
        pass


def _inputs() -> dict:
    return {"team": "Boreas", "audience": "exec", "artifacts": artifacts_for("Boreas", [15])}


def test_run_emits_one_run_span_and_three_node_spans():
    tracer = RecordingTracer()
    state = run(_inputs(), tracer=tracer)
    assert "graph:run" in tracer.spans
    assert "node:retrieval" in tracer.spans
    assert "node:risk" in tracer.spans
    assert "node:report_writer" in tracer.spans
    assert state["report"] is not None  # tracing does not change the result


def test_run_without_tracer_still_produces_a_report():
    state = run(_inputs())
    assert state["report"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_graph_tracing.py -v`
Expected: FAIL with `TypeError: run() got an unexpected keyword argument 'tracer'`

- [ ] **Step 3: Add tracing to the builder**

In `sprintsight/graph/builder.py`, add this import near the top (with the other `sprintsight` imports):

```python
from sprintsight.evals.tracing import NoOpTracer, Tracer, get_tracer
```

Add this helper above `build_graph`:

```python
def _traced(node: Callable[[GraphState], dict], name: str, tracer: Tracer):
    """Wrap a node so each invocation opens a span. No-op tracer makes this free."""

    def wrapped(state: GraphState) -> dict:
        with tracer.span(f"node:{name}"):
            return node(state)

    return wrapped
```

Replace `build_graph` with the tracer-aware version:

```python
def build_graph(
    writer: ReportWriter = compose,
    make_retriever: RetrieverFactory = default_make_retriever,
    k: int = 5,
    tracer: Tracer | None = None,
) -> CompiledStateGraph:
    """Compile the linear three-node graph with the writer/retriever injected.

    Each node is wrapped in a span; the default no-op tracer keeps CI offline and free.
    """
    tracer = tracer or NoOpTracer()
    g = StateGraph(GraphState)
    g.add_node(
        "retrieval",
        _traced(partial(retrieval_node, make_retriever=make_retriever, k=k), "retrieval", tracer),
    )
    g.add_node("risk", _traced(risk_node, "risk", tracer))
    g.add_node("report_writer", _traced(partial(report_writer_node, writer=writer), "report_writer", tracer))
    g.add_edge(START, "retrieval")
    g.add_edge("retrieval", "risk")
    g.add_edge("risk", "report_writer")
    g.add_edge("report_writer", END)
    return g.compile()
```

Replace `run` with the tracer-aware version (one `graph:run` parent span; `get_tracer()` returns a real tracer only when Langfuse keys are set, else no-op):

```python
def run(
    inputs: dict,
    *,
    writer: ReportWriter = compose,
    make_retriever: RetrieverFactory = default_make_retriever,
    k: int = 5,
    tracer: Tracer | None = None,
) -> GraphState:
    """Invoke the graph for one {team, [audience], artifacts} input -> final state."""
    tracer = tracer or get_tracer()
    graph = build_graph(writer=writer, make_retriever=make_retriever, k=k, tracer=tracer)
    init: GraphState = {
        "team": inputs["team"],
        "audience": inputs.get("audience", DEFAULT_AUDIENCE),
        "artifacts": inputs["artifacts"],
    }
    try:
        with tracer.span("graph:run"):
            return graph.invoke(init)
    finally:
        tracer.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_graph_tracing.py tests/test_graph.py tests/test_graph_evals.py -v`
Expected: PASS (existing graph tests still green; the no-op default leaves them unchanged)

- [ ] **Step 5: Write the ADR**

Create `docs/adr/ADR-0003-graph-tracing.md` (short, house style of `docs/adr/ADR-0001-three-agent-graph.md`): decision = the graph builder takes an optional `Tracer`, defaulting to no-op so CI stays offline; each node and the whole run emit spans; rationale = end-to-end observability of a run for diagnosing eval failures, reusing the existing `tracing.py` adapter; consequence = no new dependency, no behaviour change on the default path, spans carry report text and team ids only when Langfuse is configured (ZDR, opt-in). No em dashes.

- [ ] **Step 6: Run ruff and commit**

```bash
.venv/bin/ruff check sprintsight/graph/builder.py tests/test_graph_tracing.py
git add sprintsight/graph/builder.py tests/test_graph_tracing.py docs/adr/ADR-0003-graph-tracing.md
git commit -m "feat(graph): per-node tracing spans via optional Tracer (no-op default) [SS-7]"
```

---

## Task 4: Runner wiring (advisory --judge + live calibration runner)

**Files:**
- Modify: `scripts/run_report_eval.py`
- Create: `scripts/run_calibration.py`
- Test: `tests/test_judge_runner.py`

**Interfaces:**
- Consumes: `make_judge` (judge), `build_cases` (`sprintsight.evals.report`), `run_calibration` (calibration), `graph_writer`/`compose`/`make_llm_writer` (existing).
- Produces: an advisory `--judge` branch on the report-eval runner (never changes exit code) and `scripts/run_calibration.py` (exit 2 without a key, exit 0/1 on calibration result).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_judge_runner.py
import importlib


def test_judge_pass_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mod = importlib.import_module("scripts.run_report_eval")
    # The advisory pass must no-op (print a skip notice) and never raise when unkeyed.
    mod._run_judge_pass(lambda inputs: None)
    out = capsys.readouterr().out
    assert "judge" in out.lower() and "skip" in out.lower()
```

Note: `scripts/` has no `__init__.py`; confirm `import scripts.run_report_eval` resolves from the repo root (pytest `rootdir` is the repo). If it does not, mark this test `import` via `importlib.util` against the file path; otherwise the direct import is fine.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_judge_runner.py -v`
Expected: FAIL with `AttributeError: module 'scripts.run_report_eval' has no attribute '_run_judge_pass'`

- [ ] **Step 3: Add the advisory judge pass to the report-eval runner**

In `scripts/run_report_eval.py`, add this function above `main`:

```python
def _run_judge_pass(writer) -> None:
    """Advisory LLM-judge readability pass. Key-gated; never changes the exit code."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key.startswith("sk-ant-") or len(key) < 50:
        print("\n[--judge] skipped: no real ANTHROPIC_API_KEY (advisory, CI-safe).")
        return
    from sprintsight.evals.judge import make_judge
    from sprintsight.evals.report import build_cases

    judge = make_judge()
    print("\nReadability (advisory, LLM-judge):")
    for case in build_cases():
        report = writer(case.inputs)
        if report is None or report.insufficient_evidence:
            print(f"  {case.name:16} n/a (insufficient evidence)")
            continue
        score = judge(report, case.inputs.get("audience", "programme"))
        flag = "PASS" if score.passes else "below-bar"
        dims = ", ".join(f"{d}={score.scores[d]}" for d in score.scores)
        print(f"  {case.name:16} {flag}  mean={score.mean:.1f}  [{dims}]")
```

Then, in `main`, after the existing per-case print loop and before `return`, add:

```python
    if "--judge" in sys.argv:
        _run_judge_pass(_select_writer())
```

(`_select_writer` already exists and returns the graph writer; the advisory pass reuses it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_judge_runner.py -v`
Expected: PASS

- [ ] **Step 5: Create the live calibration runner**

```python
# scripts/run_calibration.py
"""Grade the readability judge against the calibration anchors (Stage 4, SS-7). Live, key-gated.

    .venv/bin/python scripts/run_calibration.py

Exits 0 only if the judge ranks every anchor as expected (good -> pass, bad -> below-bar),
1 if it does not, 2 if no real ANTHROPIC_API_KEY is set so CI never calls the API.
"""

import json
import os
import sys

from sprintsight.evals.calibration import run_calibration
from sprintsight.evals.judge import make_judge


def main() -> int:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key.startswith("sk-ant-") or len(key) < 50:
        print("ERROR: run_calibration needs a real ANTHROPIC_API_KEY in the environment.")
        return 2
    report = run_calibration(make_judge())
    print(json.dumps(report.summary(), indent=2))
    print("\nPer-anchor:")
    for r in report.results:
        verdict = "PASS" if r.passed else "FAIL"
        detail = r.assertions[0].detail if r.assertions else r.error
        print(f"  {r.name:16} {verdict}  {detail}")
    return 0 if report.pass_rate == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Smoke-run both scripts unkeyed and commit**

```bash
.venv/bin/python scripts/run_report_eval.py --judge
```
Expected: deterministic scoreboard (still green), then `[--judge] skipped: no real ANTHROPIC_API_KEY`.

```bash
.venv/bin/python scripts/run_calibration.py; echo "exit=$?"
```
Expected: `ERROR: run_calibration needs a real ANTHROPIC_API_KEY...` and `exit=2`.

```bash
.venv/bin/ruff check scripts/run_report_eval.py scripts/run_calibration.py tests/test_judge_runner.py
git add scripts/run_report_eval.py scripts/run_calibration.py tests/test_judge_runner.py
git commit -m "feat(eval): advisory --judge pass + live calibration runner [SS-7]"
```

---

## Task 5: Docs and handover

**Files:**
- Modify: `HANDOVER.md`
- Modify: `LEARNING-LOG.md`

- [ ] **Step 1: Add a LEARNING-LOG entry on LLM-as-judge**

Append `## Entry 4 (2026-06-19): LLM-as-judge (grading the soft stuff)` to `LEARNING-LOG.md`. Plain English, no em dashes. Cover: deterministic evals check one right answer; some qualities (readable? right tone?) have none, so a second AI grades the prose against a rubric; the trap is "AI marking its own homework", which we avoid by (1) a separate prompt/role from the writer and (2) grading the judge first against known good/bad anchors (the calibration meta-eval) before we trust it; advisory now, gate later. One analogy: deterministic eval = multiple-choice auto-marked; LLM-judge = an essay graded by a second examiner against a marking rubric, and we test that examiner on papers we already graded.

- [ ] **Step 2: Update HANDOVER.md**

Update the dated header line and the "Where we are" section: Stage 4 (Observability + Evals, Epic SS-7) in progress / done; readability judge (advisory, key-gated) plus calibration meta-eval added; per-node graph tracing via optional Tracer (no-op default, CI offline); both new eval modules green in CI with fakes, live paths key-gated. Note what is deferred (promoting the judge to a hard gate after calibration proves out; Langfuse dashboards). No em dashes.

- [ ] **Step 3: Full verification before handover**

```bash
.venv/bin/python -m pytest -q
```
Expected: all pass, only key-gated live tests skipped.

```bash
.venv/bin/ruff check .
```
Expected: clean.

```bash
.venv/bin/python scripts/run_report_eval.py; echo "report-eval exit=$?"
```
Expected: 4/4 green, `exit=0`.

```bash
.venv/bin/python scripts/run_watermelon_eval.py; echo "watermelon exit=$?"
```
Expected: green, `exit=0`.

- [ ] **Step 4: Commit**

```bash
git add HANDOVER.md LEARNING-LOG.md
git commit -m "docs: Stage 4 handover + LEARNING-LOG entry on LLM-as-judge [SS-7]"
```

---

## Self-Review notes (coverage map spec -> task)

- Spec section 1 (reuse existing tracing/harness): Task 3 reuses `tracing.py`; Tasks 1-2 reuse the harness.
- Spec section 3 (judge interface, rubric, pass bar, model, isolation, key-gating): Task 1.
- Spec section 4 (calibration anchors + meta-eval, identity-stable fixtures): Task 2.
- Spec section 5 (one trace per run, three node spans, optional tracer, no-op default): Task 3.
- Spec section 6 (CI-safe: default offline, opt-in `--judge`, tracing off by default): Tasks 3 and 4.
- Spec section 7 (eval-first order): each task is TDD red-then-green; calibration (Task 2) is the meta-eval.
- Spec section 8 (component boundaries): judge / calibration / tracing / runner are separate files, each testable alone.
- Spec section 9 (risks): advisory-first (Task 1 bar is non-gating), separate prompt (Task 1 `_SYSTEM`), key-gating (Tasks 1/4), least-data tracing (Task 3 ADR).
- Spec section 10 (Done means): Task 5 full verification; Jira transition handled by the controller, not a code task.

**Jira (controller, outside the subagent tasks):** create a Story under Epic SS-7, keep it in In Progress during the build, move to In Review for the eval run, then Done with a completion comment once all five tasks are committed and verification is green.
