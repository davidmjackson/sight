# Web LLM Writer Switch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the web drill-in page serve real AI-written reports when deliberately enabled by an env flag, otherwise keep today's offline `compose` behaviour exactly.

**Architecture:** Add a call-time gate in `sprintsight/web/service.py` that selects the LLM writer only when `SPRINTSIGHT_WEB_LLM=on` and a real Anthropic key is present, else the existing `_writer` seam (default `compose`). Wrap the report-shaping in an in-memory cache keyed by `(team, audience)` so repeat loads and audience switches do not re-call the writer. No routes, templates, or report contract change.

**Tech Stack:** Python 3, FastAPI (untouched here), pytest, existing `make_llm_writer` from `sprintsight/report/llm_writer.py`.

## Global Constraints

- Web stays deterministic and offline by default. Gate opens ONLY when `SPRINTSIGHT_WEB_LLM == "on"` AND `ANTHROPIC_API_KEY` starts with `sk-ant-` and is longer than 50 chars.
- Gate is read at call time (inside functions), never at import time, so tests control it via `monkeypatch.setenv` / `delenv`.
- No new persisted data. Cache is a module-level dict, in-memory, cleared on restart.
- Reuse the LLM writer's existing per-section and over-cap fallback. Add no new fallback logic.
- No changes to routes (`app.py`), templates, the `Report` contract, audience profiles, or the served `TeamDetail` shape.
- No em dashes in any David-facing prose (HANDOVER, learning-queue line).
- Tests assert the served contract (which writer is selected, cache call-counts, served sections), never pixels or live API output.

---

### Task 1: Gate + writer selection

**Files:**
- Modify: `sprintsight/web/service.py` (imports near line 9-17; add gate helpers after line 43; change `_report_for` at line 187-198)
- Test: `tests/web/test_service.py` (append)

**Interfaces:**
- Consumes: `make_llm_writer` from `sprintsight.report.llm_writer`; existing `compose`, `ReportWriter`, `_writer` seam.
- Produces: `_llm_enabled() -> bool`, `_has_real_key() -> bool`, `_active_writer() -> ReportWriter`. `_report_for` now calls `_active_writer()` instead of `_writer` directly.

- [ ] **Step 1: Write the failing tests**

First, add the `compose` import at the TOP of `tests/web/test_service.py`, directly under the
existing `from sprintsight.web import service` line (keeping it at module top avoids ruff E402):

```python
from sprintsight.web import service
from sprintsight.report.writer import compose
```

Then append the test functions to the end of `tests/web/test_service.py`:

```python
def _real_key():
    return "sk-ant-" + "x" * 60  # 67 chars: passes the shape check


def test_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", _real_key())
    assert service._llm_enabled() is False
    assert service._active_writer() is compose


def test_llm_enabled_needs_flag_and_key(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_WEB_LLM", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", _real_key())
    assert service._llm_enabled() is True
    assert service._active_writer() is not compose


def test_llm_flag_on_but_no_key_stays_off(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_WEB_LLM", "on")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert service._llm_enabled() is False
    assert service._active_writer() is compose


def test_llm_key_present_but_flag_off_stays_off(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", _real_key())
    assert service._llm_enabled() is False


def test_llm_rejects_fake_key_shape(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_WEB_LLM", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    assert service._llm_enabled() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_service.py -k "llm" -v`
Expected: FAIL with `AttributeError: module 'sprintsight.web.service' has no attribute '_llm_enabled'`

- [ ] **Step 3: Add the imports and gate helpers**

In `sprintsight/web/service.py`, add `import os` to the top imports (after `import logging` on line 9):

```python
import logging
import os
```

Add `make_llm_writer` to the report imports (the existing line 17 imports from `sprintsight.report.writer`); add a new import line beneath it:

```python
from sprintsight.report.writer import ReportWriter, compose
from sprintsight.report.llm_writer import make_llm_writer
```

After `normalize_audience` (after line 43), add:

```python
_LLM_FLAG = "SPRINTSIGHT_WEB_LLM"


def _has_real_key() -> bool:
    """A real Anthropic key has the sk-ant- shape and real length; blank/fake keys do not."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key.startswith("sk-ant-") and len(key) > 50


def _llm_enabled() -> bool:
    """True only when the brain is deliberately on AND a real key is present (fail-safe)."""
    return os.environ.get(_LLM_FLAG) == "on" and _has_real_key()


def _active_writer() -> ReportWriter:
    """The writer this request should use: the LLM writer when the gate is open, else the
    injected/default seam (compose offline)."""
    if _llm_enabled():
        return make_llm_writer()
    return _writer
```

- [ ] **Step 4: Point `_report_for` at the resolver**

In `sprintsight/web/service.py`, change the writer call inside `_report_for` (line 191) from:

```python
    report = _writer({"team": team, "audience": audience, "artifacts": arts})
```

to:

```python
    report = _active_writer()({"team": team, "audience": audience, "artifacts": arts})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_service.py -k "llm" -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Run the full web service test file (regression)**

Run: `python -m pytest tests/web/test_service.py -v`
Expected: PASS (all existing tests still green; offline path unchanged)

- [ ] **Step 7: Commit**

```bash
git add sprintsight/web/service.py tests/web/test_service.py
git commit -m "feat(stage6): key-gated LLM writer selection for the web app [SS-6]"
```

---

### Task 2: In-memory report cache

**Files:**
- Modify: `sprintsight/web/service.py` (add cache dict + `clear_report_cache`; rework `_report_for` body at line 187-198)
- Modify: `tests/web/conftest.py` (add autouse cache-clear fixture)
- Test: `tests/web/test_service.py` (append)

**Interfaces:**
- Consumes: `_active_writer()`, `ReportSection`, `EvidenceItem`, `_ordered_section_keys`, `_report_sources`, `heading_for` (all already in service.py).
- Produces: `_report_cache: dict[tuple[str, str], tuple[list[ReportSection], list[EvidenceItem], bool]]`, `clear_report_cache() -> None`. `_report_for` returns the same tuple type as before but memoized.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_service.py`:

```python
def test_report_cache_calls_writer_once_per_key(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    calls = []

    def counting(inputs):
        calls.append(inputs["audience"])
        return compose(inputs)

    monkeypatch.setattr(service, "_writer", counting)
    service.team_detail("atlas", "programme")
    service.team_detail("atlas", "programme")
    assert calls == ["programme"]  # second call served from cache


def test_report_cache_separates_audiences(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    calls = []

    def counting(inputs):
        calls.append(inputs["audience"])
        return compose(inputs)

    monkeypatch.setattr(service, "_writer", counting)
    service.team_detail("atlas", "programme")
    service.team_detail("atlas", "exec")
    assert calls == ["programme", "exec"]  # distinct keys, both computed


def test_clear_report_cache_forces_recompute(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    calls = []

    def counting(inputs):
        calls.append(inputs["audience"])
        return compose(inputs)

    monkeypatch.setattr(service, "_writer", counting)
    service.team_detail("atlas", "programme")
    service.clear_report_cache()
    service.team_detail("atlas", "programme")
    assert calls == ["programme", "programme"]


def test_offline_served_report_matches_compose(monkeypatch):
    # With the gate off, the served sections equal what compose produces directly.
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    from sprintsight.evals.fixtures import artifacts_for
    from sprintsight.report.render import heading_for

    d = service.team_detail("atlas", "programme")
    report = compose({"team": "Atlas", "audience": "programme",
                      "artifacts": artifacts_for("Atlas", [14, 15])})
    served = {s.heading: s.body for s in d.report_sections}
    expected = {heading_for(k): v for k, v in report.sections.items()}
    assert served == expected
```

- [ ] **Step 2: Add the autouse cache-clear fixture**

In `tests/web/conftest.py`, append:

```python
@pytest.fixture(autouse=True)
def _clear_report_cache():
    from sprintsight.web import service
    service.clear_report_cache()
    yield
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_service.py -k "cache or offline_served" -v`
Expected: FAIL with `AttributeError: ... has no attribute 'clear_report_cache'`

- [ ] **Step 4: Add the cache and rework `_report_for`**

In `sprintsight/web/service.py`, add the cache dict next to the seam (after the `_active_writer` block from Task 1):

```python
_report_cache: dict[tuple[str, str], tuple[list[ReportSection], list[EvidenceItem], bool]] = {}


def clear_report_cache() -> None:
    """Drop all memoized reports. Used between tests; production clears on restart."""
    _report_cache.clear()
```

Replace the body of `_report_for` (lines 187-198) with:

```python
def _report_for(
    team: str, audience: str, arts: dict[str, Artifact]
) -> tuple[list[ReportSection], list[EvidenceItem], bool]:
    """Run the writer seam and shape its report for display, memoized per (team, audience)."""
    cache_key = (team, audience)
    cached = _report_cache.get(cache_key)
    if cached is not None:
        return cached
    report = _active_writer()({"team": team, "audience": audience, "artifacts": arts})
    if report.insufficient_evidence:
        result: tuple[list[ReportSection], list[EvidenceItem], bool] = ([], [], True)
    else:
        sections = [
            ReportSection(heading_for(k), report.sections[k])
            for k in _ordered_section_keys(audience, report.sections)
        ]
        result = (sections, _report_sources(report, arts), False)
    _report_cache[cache_key] = result
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_service.py -k "cache or offline_served" -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Run all web tests (regression across pages + api + service)**

Run: `python -m pytest tests/web -v`
Expected: PASS (all green; the autouse fixture keeps the cache from leaking between tests)

- [ ] **Step 7: Commit**

```bash
git add sprintsight/web/service.py tests/web/conftest.py tests/web/test_service.py
git commit -m "feat(stage6): in-memory report cache per (team, audience) [SS-6]"
```

---

### Task 3: Full-suite verification, lint, and governance docs

**Files:**
- Modify: `HANDOVER.md` (state + Learning queue line)
- No code changes in this task.

**Interfaces:**
- Consumes: nothing new. This task proves the whole slice and records it.

- [ ] **Step 1: Run the entire test suite**

Run: `python -m pytest -q`
Expected: PASS. Baseline was 165 passed + 3 skipped; this slice adds 9 new web/service tests, so expect 174 passed + 3 skipped (the live LLM test stays skipped without a real key).

- [ ] **Step 2: Run the linter**

Run: `ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Confirm the deterministic eval gates still pass**

Run: `python scripts/run_report_eval.py`
Expected: report eval 4/4 (offline `compose` path unchanged; this is the CI gate).

- [ ] **Step 4: Update HANDOVER.md state**

In `HANDOVER.md`, update the "Where we are" state to record: the web app can now serve real AI-written reports behind the `SPRINTSIGHT_WEB_LLM=on` + real-key gate; default stays offline/compose; in-memory cache per (team, audience); routes/templates/contract unchanged; security note that this is the first live LLM call path from the web app (off by default, key-gated, ZDR, no new persisted data).

- [ ] **Step 5: Add one Learning queue line to HANDOVER.md**

Append one line to the `Learning queue` section of `HANDOVER.md` (flag only, do not teach, do not touch LEARNING-LOG.md):

```
web live-LLM gate | the web app can now make real AI calls, switched on only by an env flag plus a real key (fail-safe, offline by default) | sprintsight/web/service.py _llm_enabled | 2026-06-22
```

- [ ] **Step 6: Commit**

```bash
git add HANDOVER.md
git commit -m "docs(stage6): HANDOVER + learning-queue flag for web live-LLM gate [SS-6]"
```

---

## Notes for the executor

- The gate is intentionally evaluated at call time inside `_llm_enabled()`; do not hoist it to a module-level constant or the env-based tests and runtime toggling break.
- `_active_writer()` returns `make_llm_writer()` (constructs a closure only, no network) when the gate is open. The selection tests assert identity (`is not compose`) and never invoke it, so they make no API call.
- The autouse `_clear_report_cache` fixture is what keeps the module-level cache from leaking state across tests. If a cache test ever flakes, confirm that fixture is present and in `tests/web/conftest.py`.
- Live verification (optional, manual, costs money): set `SPRINTSIGHT_WEB_LLM=on` with a real key, run the app, open a team drill-in, and confirm the section prose differs from the offline `compose` wording while sources and the audience sections stay identical. Not part of CI.
```
