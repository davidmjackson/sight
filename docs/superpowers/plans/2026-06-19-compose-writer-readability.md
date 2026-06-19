# Compose Writer Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LLM-as-judge readability eval go green on our real reports by fixing the deterministic `compose` writer, without inventing any facts.

**Architecture:** Three targeted changes. (1) A new shared renderer turns snake_case section keys into human headings, and the judge reads through it. (2) `compose` renders multi-item RAID sections as a clean list instead of one run-together blob. (3) The exec "ask" becomes a grounded forward-looking next step keyed on whether risks are logged. Section keys stay unchanged so the deterministic gate stays green.

**Tech Stack:** Python 3.11, pytest, ruff. No new dependencies.

## Global Constraints

- No em dashes in any David-facing doc (use commas, periods, parentheses). Code/report content is exempt but prefer clean prose.
- Section keys are the machine contract: do NOT rename `overall_rag`, `top_risks`, `ask`, `risks`, `dependencies`, `milestones`, `sprint_metrics`, `ticket_progress`, `blockers`. They are asserted in `tests/test_report_writer.py` and listed in `sprintsight/report/audience.py` `required_sections`.
- No invented facts. The exec ask references only risks already logged and the RAG status already parsed. No invented owners, dates, or decisions.
- Exec word cap is 150 words (`audience.py` PROFILES["exec"].max_words); exec text must contain no ticket ids and no sprint-mechanics terms (`burndown`, `velocity`, `story points`, `points`). The deterministic report eval enforces this; keep it green.
- The deterministic evals (`scripts/run_watermelon_eval.py` and `scripts/run_report_eval.py`) are the CI gate and must stay green offline. The judge is advisory and key-gated; it is NOT promoted to a gate in this arc.
- Run all commands with the venv: `.venv/bin/python` and `.venv/bin/pytest` (or `.venv/bin/ruff`).

---

### Task 1: Shared human-heading renderer, and route the judge through it

**Files:**
- Create: `sprintsight/report/render.py`
- Create: `tests/test_render.py`
- Modify: `sprintsight/evals/judge.py:63-65` (`_user_prompt`)

**Interfaces:**
- Produces: `SECTION_TITLES: dict[str, str]`, `heading_for(key: str) -> str`, `render_report_markdown(report: Report) -> str` in `sprintsight/report/render.py`.
- Consumes: `sprintsight.report.contract.Report` (fields `team`, `audience`, `sections: dict[str,str]`, `claims`, `insufficient_evidence`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render.py`:

```python
from sprintsight.report.contract import Report
from sprintsight.report.render import heading_for, render_report_markdown


def test_render_maps_keys_to_human_headings():
    r = Report(team="Boreas", audience="exec",
               sections={"overall_rag": "Green.", "ask": "Go."})
    md = render_report_markdown(r)
    assert "## Overall status" in md
    assert "## Recommended next step" in md
    assert "overall_rag" not in md  # raw key never shown


def test_render_covers_every_contract_key():
    # Every section key any profile can emit has a human title (no raw snake_case leaks).
    for key in ("overall_rag", "top_risks", "ask", "risks", "dependencies",
                "milestones", "sprint_metrics", "ticket_progress", "blockers"):
        assert heading_for(key) != key, f"missing human title for {key}"


def test_render_unknown_key_falls_back_to_key():
    r = Report(team="Boreas", audience="exec", sections={"weird_key": "v"})
    assert "## weird_key" in render_report_markdown(r)


def test_render_empty_sections():
    assert render_report_markdown(Report(team="Boreas", audience="exec")) == "(no sections)"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.report.render'`.

- [ ] **Step 3: Create the renderer**

Create `sprintsight/report/render.py`:

```python
"""Human-readable markdown rendering for a Report.

The keys in `Report.sections` are the machine contract (audience.py
`required_sections`, asserted by the report-quality eval), so they stay
snake_case. This module is the SINGLE place that turns those keys into the
human headings a reader (or the LLM-judge) should see. One renderer, reused by
the judge and any future display surface, instead of heading logic buried in
the eval.
"""

from sprintsight.report.contract import Report

SECTION_TITLES: dict[str, str] = {
    "overall_rag": "Overall status",
    "top_risks": "Top risks",
    "ask": "Recommended next step",
    "risks": "Risks",
    "dependencies": "Dependencies",
    "milestones": "Milestones",
    "sprint_metrics": "Sprint metrics",
    "ticket_progress": "Ticket progress",
    "blockers": "Blockers",
}


def heading_for(key: str) -> str:
    """Human title for a section key; unknown keys fall back to the key unchanged."""
    return SECTION_TITLES.get(key, key)


def render_report_markdown(report: Report) -> str:
    """Render a Report's sections as markdown with human headings."""
    if not report.sections:
        return "(no sections)"
    return "\n\n".join(f"## {heading_for(k)}\n{v}" for k, v in report.sections.items())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_render.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Route the judge through the renderer**

In `sprintsight/evals/judge.py`, add the import near the top (after the existing `from sprintsight.report.contract import Report`):

```python
from sprintsight.report.render import render_report_markdown
```

Replace `_user_prompt` (currently lines 63-65):

```python
def _user_prompt(report: Report, audience: str) -> str:
    body = render_report_markdown(report)
    return f"Audience: {audience}.\nReport for team {report.team}:\n\n{body}"
```

(The old `body or '(no sections)'` fallback is no longer needed: `render_report_markdown` returns `"(no sections)"` for an empty report.)

- [ ] **Step 6: Add the judge-wiring test**

Append to `tests/test_judge.py`:

```python
def test_judge_prompt_uses_human_headings_not_raw_keys():
    captured = {}

    def grader(system, user, schema):
        captured["user"] = user
        return {d: {"score": 4, "reason": "x"} for d in DIMENSIONS}

    report = Report(team="Boreas", audience="exec",
                    sections={"overall_rag": "Green.", "ask": "No decision."})
    make_judge(grade=grader)(report, "exec")
    assert "## Overall status" in captured["user"]
    assert "overall_rag" not in captured["user"]
```

- [ ] **Step 7: Run the judge + render tests and full suite**

Run: `.venv/bin/pytest tests/test_judge.py tests/test_render.py -v`
Expected: PASS (existing judge tests still green; new wiring test green).

- [ ] **Step 8: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/report/render.py sprintsight/evals/judge.py tests/test_render.py tests/test_judge.py`
Expected: no errors.

```bash
git add sprintsight/report/render.py tests/test_render.py sprintsight/evals/judge.py tests/test_judge.py
git commit -m "feat(report): shared human-heading renderer; judge reads through it [SS-7]"
```

---

### Task 2: Split run-together risks into a clean list

**Files:**
- Modify: `sprintsight/report/writer.py` (add `_as_list`, use it in `_compose_sections`, lines 160-186)
- Test: `tests/test_report_writer.py`

**Interfaces:**
- Produces: `_as_list(items: list[str]) -> str` in `writer.py` (module-private helper).
- Consumes: `_grounded_facts`, `_compose_sections`, `Facts` (already in `writer.py`); `artifacts_for` (already imported in the test).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report_writer.py`:

```python
def test_top_risks_render_each_risk_on_its_own_line():
    from sprintsight.report.writer import _compose_sections, _grounded_facts
    f = _grounded_facts(
        {"team": "Boreas", "audience": "exec", "artifacts": artifacts_for("Boreas", [15])}
    )
    s = _compose_sections(f)
    lines = [ln for ln in s["top_risks"].splitlines() if ln.strip()]
    assert len(lines) >= 2, "Boreas exec has multiple risks; they must not run together"
    assert all(ln.startswith("- ") for ln in lines), "each risk is its own bullet"
```

(`_grounded_facts` is already imported at the top of the test file; the local import of `_compose_sections` keeps this test self-contained.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_report_writer.py::test_top_risks_render_each_risk_on_its_own_line -v`
Expected: FAIL (today `top_risks` is one space-joined line, so `len(lines) == 1`).

- [ ] **Step 3: Add the `_as_list` helper**

In `sprintsight/report/writer.py`, add this helper just above `_compose_sections` (after `_grounded_facts`):

```python
def _as_list(items: list[str]) -> str:
    """Render RAID-derived items as a clean markdown bullet list, one per line.

    Replaces the old ' '.join(...) that ran separate risks together into one blob.
    Each item gets a single trailing period (existing trailing periods/spaces are
    normalised first).
    """
    return "\n".join(f"- {i.rstrip('. ').strip()}." for i in items)
```

- [ ] **Step 4: Use `_as_list` for every multi-item section**

In `_compose_sections`, replace the three `" ".join(...)` calls for RAID lists.

Exec branch:

```python
        top = f.risks[:3]
        sections["top_risks"] = _as_list(top) if top else "No material risks reported."
```

Programme branch:

```python
        sections["risks"] = _as_list(f.risks) if f.risks else "No risks logged."
        sections["dependencies"] = (
            _as_list(f.deps) if f.deps else "No external dependencies logged."
        )
```

Team branch:

```python
        sections["blockers"] = _as_list(f.risks) if f.risks else "No blockers reported."
```

(Leave `sections["milestones"]`, `sections["sprint_metrics"]`, `sections["ticket_progress"]`, and the `overall_rag` lines unchanged: they are single prose strings, not lists.)

- [ ] **Step 5: Run the new test plus the full writer + report-eval suite**

Run: `.venv/bin/pytest tests/test_report_writer.py -v`
Expected: PASS, including the existing `test_compose_sections_exec_keys` (keys unchanged).

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: exit 0, every case PASS (word counts still under the exec 150 cap; bullets add only a few tokens).

- [ ] **Step 6: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/report/writer.py tests/test_report_writer.py`
Expected: no errors.

```bash
git add sprintsight/report/writer.py tests/test_report_writer.py
git commit -m "feat(report): render multi-item RAID sections as a list, not a run-together blob [SS-7]"
```

---

### Task 3: Forward-looking exec ask, grounded in logged risks

**Files:**
- Modify: `sprintsight/report/writer.py` (add `_exec_ask`, use it in the exec branch of `_compose_sections`)
- Test: `tests/test_report_writer.py`

**Interfaces:**
- Produces: `_exec_ask(f: Facts) -> str` in `writer.py`.
- Consumes: `Facts` (fields `risks: list[str]`), already defined in `writer.py`; `PROFILES` from `sprintsight.report.audience` (test only).

**Grounding rule (from the spec):** the ask keys on whether risks are logged, NOT on the RAG colour (our real boreas-exec case is reported green yet has three logged risks). "Most exposed" = the first risk in logged order; there is no severity field to sort on, so we take the logged order as-is and do not invent a ranking. Before finalising, the implementer checks the boreas RAID order is not misleading (see Step 5); if it were, fall back to not singling one out.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_report_writer.py`:

```python
def test_exec_ask_points_to_a_logged_risk_when_risks_exist():
    from sprintsight.report.writer import _compose_sections, _grounded_facts
    f = _grounded_facts(
        {"team": "Boreas", "audience": "exec", "artifacts": artifacts_for("Boreas", [15])}
    )
    ask = _compose_sections(f)["ask"]
    assert "Recommended next step" in ask
    assert "Decision needed: none" not in ask          # the old dead end is gone
    assert f.risks[0].rstrip(". ").strip() in ask        # names a real logged risk
    assert "owned" in ask                                # forward-looking action


def test_exec_ask_with_no_risks_is_forward_but_needs_no_decision():
    from sprintsight.report.audience import PROFILES
    from sprintsight.report.writer import Facts, _exec_ask
    f = Facts(
        team="Quiet", audience="exec", profile=PROFILES["exec"],
        burndown_id="b", status_id="s", raid_id="r", metrics=None,
        rag="green", rag_cite="s", risks=[], deps=[], looking_ahead="",
        claims=[], insufficient=False,
    )
    ask = _exec_ask(f)
    assert "No decision needed this period" in ask
    assert "on track" in ask
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_report_writer.py -k exec_ask -v`
Expected: FAIL (today `ask` is the hardcoded `"Decision needed: none this period."`; `_exec_ask` does not exist).

- [ ] **Step 3: Add the `_exec_ask` helper**

In `sprintsight/report/writer.py`, add just above `_compose_sections`:

```python
def _exec_ask(f: Facts) -> str:
    """Grounded, forward-looking exec ask.

    Keys on whether risks are logged (a report can be reported green yet still carry
    risks). Names only a risk already logged and recommends an owner be confirmed; it
    invents no owner, date, or decision. Human-in-the-loop: this is recommend-only prose.
    """
    risks = f.risks[:3]
    if not risks:
        return "No decision needed this period; delivery on track."
    top = risks[0].rstrip(". ").strip()
    if len(risks) == 1:
        return (
            f"Recommended next step: one risk logged ({top}); "
            "confirm it is owned and tracked before sprint close."
        )
    return (
        f"Recommended next step: {len(risks)} risks logged (see above). "
        f"The most exposed is {top}; confirm it is owned and tracked before sprint close."
    )
```

- [ ] **Step 4: Use it in the exec branch**

In `_compose_sections`, replace the exec `ask` line:

```python
        sections["ask"] = _exec_ask(f)
```

(Replaces `sections["ask"] = "Decision needed: none this period."`.)

- [ ] **Step 5: Verify the RAID order is not misleading, then run tests + the gate**

Inspect the boreas exec risks order:

Run: `.venv/bin/python -c "from sprintsight.report.writer import _grounded_facts; from sprintsight.evals.fixtures import artifacts_for; print(_grounded_facts({'team':'Boreas','audience':'exec','artifacts':artifacts_for('Boreas',[15])}).risks[:3])"`
Expected: a list of three risk strings. Confirm the first reads like a genuine top exposure (a performance/scalability or delivery risk), not an obviously minor item. It currently is `Audit-log export performance under large tenants unproven`, which is a fair "most exposed". If a future fixture change makes the first item obviously trivial, change `_exec_ask` to drop the "The most exposed is ..." clause and instead say "the risks above need an owner confirmed before sprint close."

Run: `.venv/bin/pytest tests/test_report_writer.py -v`
Expected: PASS.

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: exit 0, all cases PASS (exec still under 150 words, no ticket ids, no mechanics terms).

- [ ] **Step 6: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/report/writer.py tests/test_report_writer.py`
Expected: no errors.

```bash
git add sprintsight/report/writer.py tests/test_report_writer.py
git commit -m "feat(report): grounded forward-looking exec ask, replacing the dead-end line [SS-7]"
```

---

### Task 4: Verify both evals and update docs

**Files:**
- Modify: `HANDOVER.md`
- Modify: `LEARNING-LOG.md`
- Modify: `docs/superpowers/specs/2026-06-19-compose-writer-readability-design.md` (append the live result)

**Interfaces:**
- Consumes: nothing new. This task runs the gates and records the outcome.

- [ ] **Step 1: Confirm the full deterministic gate is green offline**

Run: `.venv/bin/ruff check .`
Expected: no errors.

Run: `.venv/bin/pytest`
Expected: all pass (the live judge/calibration tests skip without a key).

Run: `.venv/bin/python scripts/run_watermelon_eval.py`
Expected: exit 0, watermelon 4/4.

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: exit 0, report cases PASS.

- [ ] **Step 2: Run the live judge (the target eval) and record the numbers**

This needs the real key. Export it from `.env` (no autoloader), then run the advisory judge on both writers:

Run: `set -a; . ./.env; set +a; .venv/bin/python scripts/run_report_eval.py --judge`
Expected: the Readability block prints per-case scores. Target: boreas-exec and atlas-programme each show every dimension >= 3 and mean >= 3.5 (was ~2.0). Capture the exact line for each case.

Run: `set -a; . ./.env; set +a; .venv/bin/python scripts/run_report_eval.py --llm --judge`
Expected: a sanity read on the LLM writer (not gated this arc; it inherits the human headings). Capture the numbers.

If a dimension stays below 3 for a reason that cannot be fixed without inventing facts, STOP and report it (honesty clause). Do not reword purely to game the score.

- [ ] **Step 3: Update HANDOVER.md**

Replace the Stage-4 "next step / open" note with the arc outcome: the writer-readability arc is complete on branch `writer-readability-arc`; the three compose fixes shipped (human headings via `sprintsight/report/render.py`, list-rendered RAID sections, grounded forward-looking exec ask); deterministic gate still green; live judge moved from ~2.0 to <the captured numbers>. Note the LLM-writer numbers and that judge promotion advisory->gate is still deferred.

- [ ] **Step 4: Update LEARNING-LOG.md**

Add one concept entry (plain English, no em dashes): "Why a readability eval needed a writer fix, not a judge tweak." What it is: our automated checks proved structure but were blind to whether a report reads well; the LLM-judge caught it; the honest response was to improve the writer and re-measure, not to lower the bar. Analogy: a spell-checker passing a sentence that still makes no sense to a reader. Where it shows up: `sprintsight/report/render.py`, the `_exec_ask` rule, and the `--judge` advisory pass.

- [ ] **Step 5: Append the live result to the design doc**

Add a short "Result (2026-06-19)" section to `docs/superpowers/specs/2026-06-19-compose-writer-readability-design.md` with the before/after judge numbers for boreas-exec and atlas-programme.

- [ ] **Step 6: Commit**

```bash
git add HANDOVER.md LEARNING-LOG.md docs/superpowers/specs/2026-06-19-compose-writer-readability-design.md
git commit -m "docs: record writer-readability arc result and learning-log entry [SS-7]"
```

---

## Notes for the executor

- Jira: this arc is a new SS-7 child Story. Create it and move it To Do -> In Progress at the start, In Progress -> In Review when code is done, and In Review -> Done only after Task 4's gates pass and docs are updated. Drive the board via the Composio MCP; never set Done on create; post a completion comment when marking Done. (See CLAUDE.md and the Jira memories.)
- This branch (`writer-readability-arc`) is already created off `main`.
- Do not promote the judge from advisory to a CI gate in this arc.
