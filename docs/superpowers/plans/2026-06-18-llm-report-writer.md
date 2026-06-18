# LLM-backed Report-Writer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an LLM-authored, audience-tuned report writer behind the existing `ReportWriter` seam that passes the same 4 report-eval cases `compose` passes, with grounding/citations guaranteed deterministically.

**Architecture:** Two-layer hybrid. A shared deterministic core (refactored out of `compose`) produces the grounded facts + `claims` with citations. The LLM authors only the audience-facing section *prose*; a validator falls each violating or over-cap section back to `compose`'s prose. `claims` are always deterministic, so citation/grounding/fabrication assertions pass by construction.

**Tech Stack:** Python 3.11, Anthropic SDK (Messages API, tool-use structured output, ZDR), existing eval harness (`sprintsight/evals`), pytest, ruff.

## Global Constraints

- Eval-first: no behaviour without an eval/test that pins it. (CLAUDE.md)
- `compose` stays unchanged in external behaviour and remains the CI eval gate (`scripts/run_report_eval.py` with no args → `compose`).
- The seam is `ReportWriter = Callable[[dict[str, Any]], Report]` — do not change it.
- CI must never call the Anthropic API; offline tests use an injected fake completer.
- Default model: `claude-sonnet-4-6` (configurable via factory arg). Confirm exact id + structured-output mechanism against the `claude-api` skill before writing the real completer.
- ZDR on every Anthropic request. No persistence; no logging of artifact bodies.
- Grounding values come only from `data/ground-truth/labels.yaml` via the deterministic core — never from the LLM.
- Run all commands with the project venv: `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`.

---

### Task 1: Refactor `compose` into a shared deterministic core

Extract fact-gathering and section-prose building out of `compose` into reusable helpers, so the LLM writer can call the same grounded-facts/citations logic and reuse `compose`'s prose as its fallback. `compose`'s external behaviour and output are unchanged.

**Files:**
- Modify: `sprintsight/report/writer.py`
- Test: `tests/test_report_writer.py`, `tests/test_report_eval.py` (must stay green)

**Interfaces:**
- Consumes: `parse_metrics`, `parse_reported_status`, `Metrics` (from `sprintsight.detector`); `Artifact` (from `sprintsight.evals.fixtures`); `PROFILES`, `AudienceProfile` (from `sprintsight.report.audience`); `Claim`, `Report` (from `sprintsight.report.contract`); existing module helpers `_metric_claims`, `_rag_claim`, `_risk_lines`, `_dependency_lines`, `_looking_ahead`.
- Produces (later tasks rely on these exact names/types):
  - `@dataclass Facts` with fields: `team: str`, `audience: str`, `profile: AudienceProfile`, `burndown_id: str`, `status_id: str`, `raid_id: str`, `metrics: Metrics | None`, `rag: str`, `rag_cite: str`, `risks: list[str]`, `deps: list[str]`, `looking_ahead: str`, `claims: list[Claim]`, `insufficient: bool`
  - `_grounded_facts(inputs: dict[str, Any]) -> Facts`
  - `_compose_sections(f: Facts) -> dict[str, str]`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_report_writer.py`:

```python
from sprintsight.report.writer import _compose_sections, _grounded_facts


def test_grounded_facts_boreas_exec():
    f = _grounded_facts({"team": "Boreas", "audience": "exec",
                         "artifacts": artifacts_for("Boreas", [15])})
    assert f.insufficient is False
    assert f.rag == "green"
    assert f.rag_cite == "status-boreas-s15"
    # claims are deterministic: RAG claim is always first and cited.
    assert f.claims[0].text == "Overall status: green."
    assert f.claims[0].citations == ["status-boreas-s15"]


def test_grounded_facts_echo_is_insufficient():
    f = _grounded_facts({"team": "Echo", "audience": "exec",
                         "artifacts": artifacts_for("Echo", [15])})
    assert f.insufficient is True
    assert f.claims == []


def test_compose_sections_exec_keys():
    f = _grounded_facts({"team": "Boreas", "audience": "exec",
                         "artifacts": artifacts_for("Boreas", [15])})
    sections = _compose_sections(f)
    assert set(sections) == {"overall_rag", "top_risks", "ask"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_report_writer.py -v`
Expected: FAIL — `ImportError: cannot import name '_grounded_facts'`.

- [ ] **Step 3: Refactor `writer.py`**

Add the `Facts` dataclass and helpers, and rewrite `compose` to delegate. Keep all existing module-level helpers (`_metric_claims`, `_rag_claim`, `_table_descriptions`, `_risk_lines`, `_dependency_lines`, `_looking_ahead`) as they are. Add near the top:

```python
from dataclasses import dataclass


@dataclass
class Facts:
    """Deterministically grounded inputs for one report (single-sourced for compose + LLM)."""

    team: str
    audience: str
    profile: AudienceProfile
    burndown_id: str
    status_id: str
    raid_id: str
    metrics: Metrics | None
    rag: str
    rag_cite: str
    risks: list[str]
    deps: list[str]
    looking_ahead: str
    claims: list[Claim]
    insufficient: bool


def _grounded_facts(inputs: dict[str, Any]) -> Facts:
    team: str = inputs["team"]
    audience: str = inputs["audience"]
    arts: dict[str, Artifact] = inputs["artifacts"]
    profile = PROFILES[audience]
    t = team.lower()
    burndown_id = f"burndown-{t}-s15"
    status_id = f"status-{t}-s15"
    raid_id = f"raid-{t}-s15"

    if burndown_id not in arts:  # thin-data guard (fabrication gate)
        return Facts(team, audience, profile, burndown_id, status_id, raid_id,
                     None, "", "", [], [], "", [], insufficient=True)

    metrics = parse_metrics(arts[burndown_id].body)
    rag = parse_reported_status(arts[status_id].body) if status_id in arts else "green"
    rag_cite = status_id if status_id in arts else burndown_id
    risks = _risk_lines(arts, raid_id)
    deps = _dependency_lines(arts, raid_id)
    looking_ahead = _looking_ahead(arts, status_id)

    claims = [_rag_claim(rag, rag_cite)]
    if profile.name == "exec":
        claims += [Claim(r, [raid_id]) for r in risks[:3]]
    else:  # programme + team both carry metric claims and all risk claims
        claims += _metric_claims(metrics, burndown_id)
        claims += [Claim(r, [raid_id]) for r in risks]

    return Facts(team, audience, profile, burndown_id, status_id, raid_id,
                 metrics, rag, rag_cite, risks, deps, looking_ahead, claims,
                 insufficient=False)


def _compose_sections(f: Facts) -> dict[str, str]:
    sections: dict[str, str] = {}
    if f.profile.name == "exec":
        sections["overall_rag"] = f"Overall delivery status is {f.rag}."
        top = f.risks[:3]
        sections["top_risks"] = " ".join(top) if top else "No material risks reported."
        sections["ask"] = "Decision needed: none this period."
    elif f.profile.name == "programme":
        sections["overall_rag"] = f"Delivery status {f.rag}."
        sections["risks"] = " ".join(f.risks) if f.risks else "No risks logged."
        sections["dependencies"] = (
            " ".join(f.deps) if f.deps else "No external dependencies logged."
        )
        sections["milestones"] = f.looking_ahead
    else:  # team
        m = f.metrics
        sections["sprint_metrics"] = (
            f"Committed {int(m.committed)} points, "
            f"completed {int(m.completed)} points, "
            f"velocity {int(m.velocity)}, "
            f"{int(m.carry_over)} stories carried over."
        )
        sections["ticket_progress"] = (
            "Stories progressed across the sprint; carry-over items remain in flight."
        )
        sections["blockers"] = " ".join(f.risks) if f.risks else "No blockers reported."
    return sections
```

Replace the body of `compose` with:

```python
def compose(inputs: dict[str, Any]) -> Report:
    """Deterministic, audience-tuned, fully-cited report writer (the SS-1.5 subject)."""
    f = _grounded_facts(inputs)
    if f.insufficient:
        return Report(team=f.team, audience=f.audience, insufficient_evidence=True)
    return Report(team=f.team, audience=f.audience,
                  sections=_compose_sections(f), claims=f.claims)
```

- [ ] **Step 4: Run tests to verify all green**

Run: `.venv/bin/pytest tests/test_report_writer.py tests/test_report_eval.py -v`
Expected: PASS — new `_grounded_facts`/`_compose_sections` tests pass and all four existing report-eval cases still green (`compose` behaviour unchanged).

- [ ] **Step 5: Lint + full report-eval gate**

Run: `.venv/bin/ruff check sprintsight/report/writer.py && .venv/bin/python scripts/run_report_eval.py`
Expected: ruff clean; eval prints `"pass_rate": 1.0` and exits 0.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/report/writer.py tests/test_report_writer.py
git commit -m "SS-2 arc2: extract shared grounded-facts core from compose"
```

---

### Task 2: LLM writer with validation + fallback (offline, fake completer)

Build `make_llm_writer` — the heart of the arc — and test it entirely offline with an injected fake completer. No Anthropic SDK is touched in this task.

**Files:**
- Create: `sprintsight/report/llm_writer.py`
- Test: `tests/test_llm_writer.py`

**Interfaces:**
- Consumes: `Facts`, `_grounded_facts`, `_compose_sections` (Task 1); `Report` (`sprintsight.report.contract`); `ReportWriter` (`sprintsight.report.writer`); `AudienceProfile`, `TICKET_ID`, `MECHANICS_TERMS` (`sprintsight.report.audience`); `run_report_eval` (`sprintsight.evals.report`).
- Produces:
  - `Completer = Callable[[str, str, dict[str, Any]], dict[str, str]]` — `(system, user, schema) -> {section_key: prose}`
  - `make_llm_writer(complete: Completer | None = None, model: str = DEFAULT_MODEL) -> ReportWriter`
  - `DEFAULT_MODEL: str` constant
  - Module helpers: `_section_violates(text: str, profile: AudienceProfile) -> bool`, `_rendered_words(sections: dict[str, str], claims: list) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm_writer.py`:

```python
from sprintsight.evals.report import run_report_eval
from sprintsight.report.llm_writer import make_llm_writer


def _good_fake(system, user, schema):
    """Return clean one-line prose for every section key the schema requests."""
    keys = schema["properties"]["sections"]["properties"].keys()
    return {k: f"Narrative for {k}." for k in keys}


def test_llm_writer_greens_the_whole_suite():
    writer = make_llm_writer(complete=_good_fake)
    report = run_report_eval(writer)
    assert report.pass_rate == 1.0, report.summary()


def test_llm_writer_falls_back_on_ticket_id():
    # exec forbids ticket ids; a fake that injects one must be replaced by compose prose.
    def bad_fake(system, user, schema):
        keys = schema["properties"]["sections"]["properties"].keys()
        return {k: f"See ATLAS-12 for {k}." for k in keys}

    writer = make_llm_writer(complete=bad_fake)
    report = run_report_eval(writer)
    # exec case must still pass audience_fit because violating sections fell back.
    assert report.pass_rate == 1.0, report.summary()


def test_llm_writer_falls_back_when_over_cap():
    # A fake that floods exec past its 150-word cap triggers wholesale section fallback.
    def long_fake(system, user, schema):
        keys = schema["properties"]["sections"]["properties"].keys()
        return {k: ("word " * 200).strip() for k in keys}

    writer = make_llm_writer(complete=long_fake)
    report = run_report_eval(writer)
    assert report.pass_rate == 1.0, report.summary()


def test_thin_data_skips_the_llm():
    calls = []

    def spy(system, user, schema):
        calls.append(1)
        return {}

    from sprintsight.evals.fixtures import artifacts_for
    writer = make_llm_writer(complete=spy)
    rep = writer({"team": "Echo", "audience": "exec",
                  "artifacts": artifacts_for("Echo", [15])})
    assert rep.insufficient_evidence is True
    assert calls == []  # LLM never called on thin data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sprintsight.report.llm_writer'`.

- [ ] **Step 3: Write `llm_writer.py`**

```python
"""LLM-backed report writer behind the `ReportWriter` seam (Stage 2 arc 2).

Hybrid: the deterministic core (`_grounded_facts`) owns numbers, RAG status, and the
cited `claims`; the LLM authors only section prose. A validator falls violating or
over-cap sections back to `compose`'s prose, so every report-eval assertion holds by
construction. The Anthropic completer is injected, so CI/tests run with a fake.
"""

import re
from collections.abc import Callable
from typing import Any

from sprintsight.report.audience import MECHANICS_TERMS, TICKET_ID, AudienceProfile
from sprintsight.report.contract import Report
from sprintsight.report.writer import (
    Facts,
    ReportWriter,
    _compose_sections,
    _grounded_facts,
)

DEFAULT_MODEL = "claude-sonnet-4-6"  # confirm exact id via the claude-api skill (Task 3)

# (system_prompt, user_prompt, output_schema) -> {section_key: prose}
Completer = Callable[[str, str, dict[str, Any]], dict[str, str]]

_SYSTEM = (
    "You write concise, audience-tuned delivery status prose. You are given already-"
    "verified facts. Write only from those facts. Never invent numbers, dates, or ticket "
    "ids. Return one short paragraph per requested section."
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
    lines.append(f"Word budget for the whole report: {p.max_words or 'no strict cap'}.")
    if p.forbid_ticket_ids:
        lines.append("Do NOT mention any ticket ids (e.g. ABC-123).")
    if p.forbid_mechanics:
        lines.append(f"Do NOT mention sprint mechanics: {', '.join(MECHANICS_TERMS)}.")
    lines.append(f"Write these sections: {', '.join(p.required_sections)}.")
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
    if profile.forbid_ticket_ids and re.search(TICKET_ID, text):
        return True
    if profile.forbid_mechanics and any(t in text.lower() for t in MECHANICS_TERMS):
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


def _anthropic_completer(model: str) -> Completer:  # real client; built in Task 3
    raise NotImplementedError("Anthropic completer is wired in Task 3")
```

Note: the fake test returns a bare `{section_key: prose}` dict; the real completer (Task 3) returns `{"sections": {...}}`. `write` accepts either shape via the `prose.get("sections", prose)` line.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_llm_writer.py -v`
Expected: PASS — all four tests green (suite greens with the good fake; both fallbacks keep it green; thin data skips the completer).

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check sprintsight/report/llm_writer.py tests/test_llm_writer.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/report/llm_writer.py tests/test_llm_writer.py
git commit -m "SS-2 arc2: LLM report writer with validation + per-section fallback (offline)"
```

---

### Task 3: Real Anthropic completer + live eval flag

Wire the real completer and a manual live path, without changing CI defaults. **Before writing code, invoke the `claude-api` skill** to confirm the current model id, the Messages API call shape, and structured-output via tool use.

**Files:**
- Modify: `pyproject.toml` (add `anthropic` dependency)
- Modify: `sprintsight/report/llm_writer.py` (`_anthropic_completer`)
- Modify: `scripts/run_report_eval.py` (add `--llm` flag, gated on key presence)
- Test: `tests/test_llm_writer.py` (construction + skip-if-no-key)

**Interfaces:**
- Consumes: `make_llm_writer`, `DEFAULT_MODEL` (Task 2); `run_report_eval` (`sprintsight.evals.report`); `compose` (`sprintsight.report.writer`).
- Produces: a working `_anthropic_completer(model) -> Completer`; `run_report_eval.py` runs `compose` by default and `make_llm_writer()` under `--llm`.

- [ ] **Step 1: Invoke the claude-api skill**

Use the `claude-api` skill. Confirm: exact model id for the Sonnet 4.6 default, the `anthropic` Python SDK Messages call, how to force structured output (tool use with `input_schema`, `tool_choice`), and ZDR header/param. Update `DEFAULT_MODEL` if the confirmed id differs.

- [ ] **Step 2: Add the dependency**

In `pyproject.toml`, add `anthropic` to the project dependencies array (pin a recent floor, e.g. `"anthropic>=0.40"`; confirm the current floor via the claude-api skill). Then:

Run: `.venv/bin/pip install -e .`
Expected: `anthropic` installs without conflict.

- [ ] **Step 3: Write the failing test**

Add to `tests/test_llm_writer.py`:

```python
import os

import pytest

from sprintsight.report.llm_writer import _anthropic_completer, make_llm_writer


def test_anthropic_completer_constructs_without_calling_api():
    # Building the completer must not require a network call.
    completer = _anthropic_completer("claude-sonnet-4-6")
    assert callable(completer)


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-")
    or len(os.getenv("ANTHROPIC_API_KEY", "")) < 50,
    reason="no real Anthropic key wired",
)
def test_live_llm_writer_greens_the_suite():
    from sprintsight.evals.report import run_report_eval
    report = run_report_eval(make_llm_writer())
    assert report.pass_rate == 1.0, report.summary()
```

- [ ] **Step 4: Run test to verify the construction test fails**

Run: `.venv/bin/pytest tests/test_llm_writer.py::test_anthropic_completer_constructs_without_calling_api -v`
Expected: FAIL — `NotImplementedError: Anthropic completer is wired in Task 3`.

- [ ] **Step 5: Implement `_anthropic_completer`**

Replace the stub in `sprintsight/report/llm_writer.py`. Import the SDK lazily so the module imports without `anthropic` installed for the fake-based tests. Use the call shape confirmed from the claude-api skill; the shape below is the expected structure — adjust names to the confirmed SDK:

```python
def _anthropic_completer(model: str) -> Completer:
    """Real completer: Anthropic Messages API with tool-use structured output, ZDR on."""

    def complete(system: str, user: str, schema: dict[str, Any]) -> dict[str, str]:
        import anthropic  # lazy: only needed on the live path

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        tool = {"name": "emit_report", "description": "Return the report sections.",
                "input_schema": schema}
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit_report"},
            messages=[{"role": "user", "content": user}],
            extra_headers={"anthropic-beta": "zdr"},  # confirm ZDR mechanism via claude-api skill
        )
        for block in msg.content:
            if block.type == "tool_use" and block.name == "emit_report":
                return block.input  # {"sections": {...}}
        return {}

    return complete
```

- [ ] **Step 6: Run the construction test**

Run: `.venv/bin/pytest tests/test_llm_writer.py::test_anthropic_completer_constructs_without_calling_api -v`
Expected: PASS (no network call on construction).

- [ ] **Step 7: Add the `--llm` flag to the eval script**

In `scripts/run_report_eval.py`, keep `compose` as the default and select the LLM writer under `--llm`:

```python
import os
import sys

from sprintsight.evals.report import run_report_eval
from sprintsight.report.llm_writer import make_llm_writer
from sprintsight.report.writer import compose


def _select_writer() -> object:
    if "--llm" in sys.argv:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key.startswith("sk-ant-") or len(key) < 50:
            print("ERROR: --llm needs a real ANTHROPIC_API_KEY in the environment.")
            sys.exit(2)
        return make_llm_writer()
    return compose
```

Then in `main()` call `run_report_eval(_select_writer())` instead of `run_report_eval(compose)`. Leave the rest (printing, exit code) unchanged so the no-arg CI path is byte-for-byte the same.

- [ ] **Step 8: Verify CI default path unchanged + lint + full suite**

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: `"pass_rate": 1.0`, exit 0 (still `compose`).

Run: `.venv/bin/ruff check . && .venv/bin/pytest -q`
Expected: ruff clean; whole test suite green (live test is skipped without a real key).

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml sprintsight/report/llm_writer.py scripts/run_report_eval.py tests/test_llm_writer.py
git commit -m "SS-2 arc2: real Anthropic completer + --llm live eval path"
```

---

### Task 4: Live run with a real key (manual)

Prove the LLM path end-to-end against the real API. This is operator-driven; the worker pauses for the human to supply the key.

**Files:** none (runtime only).

- [ ] **Step 1: Human wires a real key**

The operator adds a real `sk-ant-…` key to `.env` via a shell variable (never pasted into chat or committed). `.env` is already gitignored — confirm with `git check-ignore .env`.

- [ ] **Step 2: Run the live eval**

Run (with `.env` exported into the environment): `.venv/bin/python scripts/run_report_eval.py --llm`
Expected: `"pass_rate": 1.0`, exit 0 — the LLM writer passes all four cases live.

- [ ] **Step 3: Spot-check the prose**

Render one report (e.g. Boreas/exec and Boreas/team) through `make_llm_writer()` and eyeball that the prose is genuinely LLM-authored, audience-distinct, and free of fabricated numbers/ids. Record the observation in HANDOVER.md.

---

## Self-Review

**Spec coverage:**
- Hybrid grounding (deterministic claims, LLM prose) → Task 1 (core) + Task 2 (writer). ✓
- Two-layer writer with per-section + report-level fallback → Task 2 (`_section_violates`, cap check). ✓
- Injected completer / fake for CI → Task 2 (`Completer`, fake tests). ✓
- Real Anthropic client, ZDR, structured output, configurable model → Task 3. ✓
- Thin-data skips LLM, no fabrication surface → Task 2 (`test_thin_data_skips_the_llm`). ✓
- `compose` unchanged + stays CI gate → Task 1 (delegates, tests stay green) + Task 3 (no-arg default). ✓
- Drop-in parity (same 4 eval cases) → Task 2 (suite greens with fake) + Task 4 (live). ✓
- Offline unit test in CI, live gated on key → Task 2 + Task 3 (skipif). ✓

**Placeholder scan:** Model id and ZDR mechanism are explicitly deferred to the claude-api skill in Task 3 Step 1 (a real lookup, not a hand-wave); the SDK call shape is shown concretely with a note to reconcile against the confirmed API. No "TODO"/"handle edge cases"/"write tests for the above" left.

**Type consistency:** `Facts`, `_grounded_facts`, `_compose_sections` defined in Task 1 and consumed by Task 2 with matching signatures. `Completer`, `make_llm_writer`, `DEFAULT_MODEL`, `_section_violates`, `_rendered_words` defined in Task 2 and consumed in Task 3. `make_llm_writer(complete=...)` keyword matches across all tests. The completer returns `{"sections": {...}}` (real) or `{section_key: prose}` (fake); `write` normalises both via `prose.get("sections", prose)`.
