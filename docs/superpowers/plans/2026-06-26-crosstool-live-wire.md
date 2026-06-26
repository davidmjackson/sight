# Cross-tool live-wire Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the `/crosstool` web page read the LIVE Jira board + GitHub repo behind a fail-safe gate, while staying offline-by-default and deterministic in CI.

**Architecture:** `crosstool_view()` gains an injectable `source` callable returning `(tickets, activity, as_of, mode)`. An `_active_source()` picks live connectors when an env gate is open (flag + real GITHUB_TOKEN + Composio key + repo/project configured), else the existing fixtures. Live failure falls back to offline with an honest `offline-failed` mode. The pure `reconcile()`, row shaping, citations, and downstream code are untouched.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, pytest. Connectors: PyGithub (lazy), Composio SDK (lazy). Reuses the existing `_writer`/`_llm_enabled` gate pattern from `service.py`.

## Global Constraints

- Python 3.11+ (uses `datetime.UTC`). Copy exact values from the spec.
- Offline is the default and the ONLY path exercised in CI. No test may touch the network.
- The deterministic eval gates must stay green: watermelon 4/4, report 4/4, cross-tool 7/7.
- Baseline test suite is 227 passed + 3 skipped; do not regress it. Run `ruff check .` clean.
- The "two data worlds" stay apart: the offline path (`service.py` burndown world + the existing fixtures) is byte-for-byte unchanged.
- Source-of-truth env names: flag `SPRINTSIGHT_CROSSTOOL_LIVE` (value `"on"`), `GITHUB_TOKEN`, `COMPOSIO_API_KEY`, `SPRINTSIGHT_CROSSTOOL_REPO` (`owner/name`), `SPRINTSIGHT_CROSSTOOL_PROJECT` (`SSSB`).
- Source tuple is `(tickets: list[dict], activity: dict[str, Activity], as_of: str, mode: str)`; `mode in {"live", "offline", "offline-failed"}`.

---

### Task 1: Shared ticket extraction

Lift `_tickets_from_artifacts` out of the CLI script (the web layer cannot import a script) into the `connect` package as the public `tickets_from_artifacts`, and point the CLI at the new home. Pure move, no behaviour change, now covered by a unit test.

**Files:**
- Create: `sprintsight/connect/jira_tickets.py`
- Modify: `scripts/run_cross_tool.py` (remove the local function, import the shared one)
- Test: `tests/connect/test_jira_tickets.py`

**Interfaces:**
- Consumes: `Artifact` (`sprintsight.evals.fixtures`), `normalize` (`sprintsight.connect.normalize`) in the test only.
- Produces: `tickets_from_artifacts(artifacts: dict[str, Artifact]) -> dict[str, dict]`, each value `{"key": str, "status": str, "team": str}`.

- [ ] **Step 1: Write the failing test**

Create `tests/connect/test_jira_tickets.py`:

```python
from sprintsight.connect.jira_tickets import tickets_from_artifacts
from sprintsight.connect.normalize import normalize


def test_tickets_from_artifacts_pulls_key_status_team():
    # normalize renders status into the body meta line: "**Status:** In Progress · ..."
    art = normalize(
        {"key": "SSSB-1", "summary": "Login flow", "status": "In Progress",
         "team": "Atlas", "sprint": 0}
    )
    tickets = tickets_from_artifacts({art.artifact_id: art})
    assert tickets == {
        "SSSB-1": {"key": "SSSB-1", "status": "In Progress", "team": "Atlas"}
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/connect/test_jira_tickets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.connect.jira_tickets'`

- [ ] **Step 3: Create the shared module**

Create `sprintsight/connect/jira_tickets.py` (lifted verbatim from `scripts/run_cross_tool.py`, renamed public):

```python
"""Shared extraction: turn corpus Artifacts into the {key, status, team} ticket dicts the
cross-tool reconciler consumes. Used by both the CLI demo and the web crosstool service.
"""

from sprintsight.evals.fixtures import Artifact


def tickets_from_artifacts(artifacts: dict[str, Artifact]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for art in artifacts.values():
        key = art.meta.get("source_ref", art.artifact_id)
        # status rides in the body's meta line: "**Status:** In Progress · ..."
        status = ""
        for line in art.body.splitlines():
            if "Status:" in line:
                status = line.split("Status:", 1)[1].split("·")[0].strip().strip("*").strip()
                break
        out[key] = {"key": key, "status": status, "team": art.team}
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/connect/test_jira_tickets.py -v`
Expected: PASS

- [ ] **Step 5: Point the CLI at the shared module**

In `scripts/run_cross_tool.py`, delete the local `_tickets_from_artifacts` function (lines 23-34) and its now-unused nothing-else, then add the import and update the call site.

Add to the imports block:

```python
from sprintsight.connect.jira_tickets import tickets_from_artifacts
```

Change the call site (was `tickets = _tickets_from_artifacts(jira.fetch())`):

```python
    tickets = tickets_from_artifacts(jira.fetch())
```

- [ ] **Step 6: Verify the CLI still imports and the suite is green**

Run: `python -c "import scripts.run_cross_tool"` (Expected: no error)
Run: `pytest tests/ -q` (Expected: still 227 passed + 3 skipped, plus the 1 new test = 228 passed)
Run: `ruff check .` (Expected: clean)

- [ ] **Step 7: Commit**

```bash
git add sprintsight/connect/jira_tickets.py tests/connect/test_jira_tickets.py scripts/run_cross_tool.py
git commit -m "refactor(stage7): share tickets_from_artifacts for web + CLI [SS-5]"
```

---

### Task 2: Source seam, gate, and honest-failure fallback

Add the injectable source to `crosstool_service.py`: a `mode` field on the summary, the gate helpers, the offline/live/active sources with the offline-failed fallback, and refactor `crosstool_view()` to read from its source. Offline default behaviour is unchanged.

**Files:**
- Modify: `sprintsight/web/crosstool_service.py`
- Test: `tests/web/test_crosstool_service.py` (append new tests)

**Interfaces:**
- Consumes: `tickets_from_artifacts` (Task 1), `JiraConnector` (`sprintsight.connect.connector`), `GitHubConnector` + `Activity` (`sprintsight.connect.github`).
- Produces:
  - `CrossToolSummary` now has `mode: str`.
  - `crosstool_view(source: Callable[[], tuple[list[dict], dict[str, Activity], str, str]] = _active_source) -> CrossToolPage`.
  - `_offline_source()`, `_live_source()`, `_active_source()`, `_crosstool_live_enabled()` module-level.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_crosstool_service.py`:

```python
from sprintsight.web import crosstool_service
from sprintsight.web.crosstool_service import _active_source


def _fake_live_source():
    # one "In Progress" ticket with no GitHub activity -> a watermelon
    tickets = [{"key": "SSSB-1", "status": "In Progress", "team": "Atlas"}]
    activity = {}
    return tickets, activity, "2026-07-01T12:00:00Z", "live"


def test_live_source_shapes_page_with_live_mode():
    page = crosstool_view(source=_fake_live_source)
    assert page.summary.mode == "live"
    assert page.summary.as_of == "2026-07-01T12:00:00Z"
    assert page.summary.checked == 1
    assert page.summary.watermelons == 1
    row = page.rows[0]
    assert row.key == "SSSB-1"
    assert row.jira_citation.startswith("Jira ")
    assert row.github_citation.startswith("GitHub:")


def test_default_source_is_offline(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_CROSSTOOL_LIVE", raising=False)
    page = crosstool_view()
    assert page.summary.mode == "offline"
    assert page.summary.checked == 4


def test_live_failure_falls_back_to_offline_failed(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_LIVE", "on")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("COMPOSIO_API_KEY", "x")
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_REPO", "owner/repo")
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_PROJECT", "SSSB")

    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(crosstool_service, "_live_source", boom)
    page = crosstool_view(source=_active_source)
    assert page.summary.mode == "offline-failed"
    assert page.summary.checked == 4  # fell back to the fixtures
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/web/test_crosstool_service.py -v`
Expected: FAIL — `_active_source` / `mode` do not exist yet (ImportError / AttributeError).

- [ ] **Step 3: Add imports and the `mode` field**

In `sprintsight/web/crosstool_service.py`, update the imports at the top:

```python
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sprintsight.connect.connector import JiraConnector
from sprintsight.connect.github import Activity, GitHubConnector, RecordedGitHubConnector
from sprintsight.connect.jira_tickets import tickets_from_artifacts
from sprintsight.crosstool import reconcile
from sprintsight.evals.watermelon import Verdict
```

Add `mode` to the summary dataclass:

```python
@dataclass(frozen=True)
class CrossToolSummary:
    checked: int
    watermelons: int
    stalled: int
    as_of: str
    mode: str
```

- [ ] **Step 4: Add the gate and the sources**

Insert ABOVE `crosstool_view` (after the `_classification` helper):

```python
_LIVE_FLAG = "SPRINTSIGHT_CROSSTOOL_LIVE"


def _crosstool_config() -> tuple[str, str] | None:
    """The configured (repo, project) for a live read, or None when either is missing."""
    repo = os.environ.get("SPRINTSIGHT_CROSSTOOL_REPO", "")
    project = os.environ.get("SPRINTSIGHT_CROSSTOOL_PROJECT", "")
    return (repo, project) if repo and project else None


def _crosstool_live_enabled() -> bool:
    """True only when the live switch is deliberately on AND every credential and the
    repo/project are present (fail-safe). Any missing piece falls back to offline."""
    return (
        os.environ.get(_LIVE_FLAG) == "on"
        and bool(os.environ.get("GITHUB_TOKEN"))
        and bool(os.environ.get("COMPOSIO_API_KEY"))
        and _crosstool_config() is not None
    )


def _offline_source() -> tuple[list[dict], dict[str, Activity], str, str]:
    """The frozen replay: two fixtures, a pinned clock. No network. Unchanged behaviour."""
    tickets = json.loads(_JIRA_FIXTURE.read_text(encoding="utf-8"))
    activity = RecordedGitHubConnector.from_file(_GITHUB_FIXTURE).fetch_activity()
    return tickets, activity, CROSSTOOL_AS_OF, "offline"


def _live_source() -> tuple[list[dict], dict[str, Activity], str, str]:
    """The live read: real Jira tickets + real GitHub activity, real clock. Gate guarantees
    the config is present before this is called."""
    repo, project = _crosstool_config()  # type: ignore[misc]
    tickets = list(tickets_from_artifacts(JiraConnector(project).fetch()).values())
    activity = GitHubConnector(repo).fetch_activity()
    return tickets, activity, datetime.now(UTC).isoformat(), "live"


def _active_source() -> tuple[list[dict], dict[str, Activity], str, str]:
    """Live when the gate is open, else offline. A live failure is honest: it falls back to the
    offline replay and reports `offline-failed` rather than 500-ing or faking live data."""
    if not _crosstool_live_enabled():
        return _offline_source()
    try:
        return _live_source()
    except Exception:
        tickets, activity, _as_of, _mode = _offline_source()
        return tickets, activity, CROSSTOOL_AS_OF, "offline-failed"
```

- [ ] **Step 5: Refactor `crosstool_view` to read from its source**

Replace the current `crosstool_view` body. The signature takes the source; the two fixture-loading lines are gone (they now live in `_offline_source`); the summary carries `mode`. The loop body is unchanged.

```python
def crosstool_view(
    source: Callable[[], tuple[list[dict], dict[str, Activity], str, str]] = _active_source,
) -> CrossToolPage:
    """Reconcile every ticket against its GitHub activity and shape the page.

    The `source` supplies (tickets, activity, as_of, mode); default `_active_source` is offline
    unless the live gate is open. Pure given its source: the web layer pairs each ticket key with
    its verdict here (a `Verdict` carries no key), so every row keeps its citation.
    """
    tickets, activity, as_of, mode = source()
    rows: list[CrossToolRow] = []
    for t in tickets:
        key, status, team = t["key"], t.get("status", ""), t.get("team", "")
        verdict = reconcile(
            {"ticket": t, "activity": activity.get(key), "as_of": as_of}
        )
        signal = verdict.signals[0] if verdict.signals else ""
        rows.append(
            CrossToolRow(
                key=key,
                team=team,
                reported_status=verdict.reported_status,
                actual_status=verdict.actual_status,
                classification=_classification(verdict),
                headline=verdict.explanation,
                jira_citation=_jira_citation(key, status),
                github_citation=_github_citation(signal),
            )
        )
    rows.sort(key=lambda r: (_SORT_RANK[r.classification], r.key))
    summary = CrossToolSummary(
        checked=len(rows),
        watermelons=sum(1 for r in rows if r.classification == "watermelon"),
        stalled=sum(1 for r in rows if r.classification == "stalled"),
        as_of=as_of,
        mode=mode,
    )
    return CrossToolPage(summary=summary, rows=rows)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/web/test_crosstool_service.py -v`
Expected: PASS, including the existing offline tests (`test_summary_counts_match_fixtures` still sees `checked==4`, `as_of=="2026-06-25T00:00:00Z"`).

- [ ] **Step 7: Run the full suite + lint**

Run: `pytest tests/ -q`
Expected: all green (228 + 3 new = 231 passed, 3 skipped). The `/api/crosstool` test still passes (the JSON simply gains a `mode` field).
Run: `ruff check .`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add sprintsight/web/crosstool_service.py tests/web/test_crosstool_service.py
git commit -m "feat(stage7): live source seam + fail-safe gate for /crosstool [SS-5]"
```

---

### Task 3: Live/offline badge on the page

Surface the `mode` as a small badge so a live demo is legible. Template-only change plus a served-HTML test.

**Files:**
- Modify: `sprintsight/web/templates/crosstool.html`
- Test: `tests/web/test_pages.py` (append one test)

**Interfaces:**
- Consumes: `page.summary.mode` and `page.summary.as_of` from Task 2.
- Produces: visible badge text; no new Python symbols.

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_pages.py` (the `client` fixture is the logged-in client already used by `test_crosstool_page_renders_summary_and_flags`):

```python
def test_crosstool_page_shows_offline_badge_by_default(client):
    resp = client.get("/crosstool")
    assert resp.status_code == 200
    assert "offline replay" in resp.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_pages.py::test_crosstool_page_shows_offline_badge_by_default -v`
Expected: FAIL — the string is not in the page yet.

- [ ] **Step 3: Add the badge to the template**

In `sprintsight/web/templates/crosstool.html`, replace the lede paragraph (line 5):

```html
<p class="lede">Jira status versus the actual GitHub activity, per ticket.
  {% if page.summary.mode == 'live' %}
    <span class="badge badge-ok" title="Read live from Jira + GitHub">live as of {{ page.summary.as_of }}</span>
  {% elif page.summary.mode == 'offline-failed' %}
    <span class="badge badge-stalled" title="Live read failed; showing the saved snapshot">offline (live read failed)</span>
  {% else %}
    <span class="badge badge-ok" title="Saved snapshot, deterministic">offline replay</span>
  {% endif %}
  <a href="/">Back to portfolio</a>.</p>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_pages.py::test_crosstool_page_shows_offline_badge_by_default -v`
Expected: PASS

- [ ] **Step 5: Run the full suite + lint**

Run: `pytest tests/ -q`
Expected: all green (232 passed, 3 skipped). Existing crosstool page tests unaffected.
Run: `ruff check .`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/web/templates/crosstool.html tests/web/test_pages.py
git commit -m "feat(stage7): live/offline badge on the /crosstool page [SS-5]"
```

---

## Final verification (after all tasks)

- [ ] Run the deterministic eval gates and confirm unchanged:
  - `python scripts/run_watermelon_eval.py` (Expected: 4/4)
  - `python scripts/run_report_eval.py` (Expected: 4/4)
  - cross-tool eval (Expected: 7/7) — use the project's eval runner for `crosstool_eval`.
- [ ] `pytest tests/ -q` green; `ruff check .` clean.
- [ ] Confirm the offline page is visually unchanged except the new badge (the burndown world and fixtures are untouched).
- [ ] Append a Learning-queue line to HANDOVER.md if the fail-safe-live pattern reuse is worth flagging (flag only; do not write LEARNING-LOG).
