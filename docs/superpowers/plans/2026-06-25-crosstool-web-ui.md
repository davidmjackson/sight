# Cross-tool watermelons + stalled in the web UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated, auth-gated `/crosstool` web page that surfaces the per-ticket cross-tool watermelon (Jira says progressing, GitHub shows no real work) and the amber stalled-PR signal, reading captured replay fixtures only.

**Architecture:** A new pure data module `sprintsight/web/crosstool_service.py` loads two captured fixtures, runs the existing `sprintsight.crosstool.reconcile()` per ticket against a pinned `as_of`, and shapes the verdicts into frozen view-models (summary + flagged-first rows with plain-English citations). A new route + JSON API + Jinja template render it. No network, no live gate, no change to the burndown world or any eval gate.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, pytest. Reuses `RecordedGitHubConnector`, `reconcile`, and the existing design-system CSS.

## Global Constraints

- No em dashes in any David-facing copy (page text, docs). Use commas, periods, parentheses.
- Offline only: no network call in any web request; no `datetime.now`/clock in `crosstool_service.py`. Determinism via the pinned constant `CROSSTOOL_AS_OF = "2026-06-25T00:00:00Z"`.
- Eval-first: the failing test is written and run (RED) before the implementation in every task.
- Do not modify: `sprintsight/crosstool.py`, `sprintsight/web/service.py`, the burndown detector, or any eval under `sprintsight/evals/`.
- Fixtures live in `data/captured/`. Resolve paths relative to the module/test file, never the CWD.
- Reuse existing CSS classes: `summary-band`, `kpi`, `kpi-alert`, `rag-green|amber|red`, `badge-watermelon|ok|muted`. One new class `badge-stalled` is added in Task 4.
- Test auth: web route tests use the `client` fixture (logged-in admin) from `tests/web/conftest.py`.

---

### Task 1: Web-demo fixtures (data) + reconcile-level guard test

Author the two captured fixtures so the page can show all three colours, and lock their meaning with a test that runs the existing reconciler directly over them.

**Files:**
- Create: `data/captured/crosstool_web_jira.json`
- Create: `data/captured/crosstool_web_github.json`
- Test: `tests/web/test_crosstool_fixtures.py`

**Interfaces:**
- Consumes: `sprintsight.crosstool.reconcile`, `sprintsight.connect.github.RecordedGitHubConnector` (both existing, unchanged).
- Produces: two fixture files whose keys (SSSB-1/2/3/7) and shapes the later tasks read. Expected verdicts as_of `2026-06-25T00:00:00Z`: SSSB-1 watermelon (no-ref), SSSB-2 watermelon (PR#12 open-unmerged), SSSB-3 clean (PR#5 merged), SSSB-7 stalled/amber (PR#20 open, quiet 17 days).

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_crosstool_fixtures.py`:

```python
import json
from pathlib import Path

from sprintsight.connect.github import RecordedGitHubConnector
from sprintsight.crosstool import reconcile

_DATA = Path(__file__).resolve().parents[2] / "data" / "captured"
AS_OF = "2026-06-25T00:00:00Z"


def _verdicts() -> dict:
    tickets = json.loads((_DATA / "crosstool_web_jira.json").read_text(encoding="utf-8"))
    activity = RecordedGitHubConnector.from_file(
        _DATA / "crosstool_web_github.json"
    ).fetch_activity()
    return {
        t["key"]: reconcile(
            {"ticket": t, "activity": activity.get(t["key"]), "as_of": AS_OF}
        )
        for t in tickets
    }


def test_web_fixtures_show_all_three_colours():
    v = _verdicts()
    assert v["SSSB-1"].is_watermelon                       # In Progress, no linked work
    assert v["SSSB-2"].is_watermelon                       # Done, PR open-unmerged
    assert v["SSSB-3"].actual_status == "green"
    assert not v["SSSB-3"].is_watermelon                   # Done, PR merged -> clean
    assert v["SSSB-7"].actual_status == "amber"            # In Progress, PR stalled
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_crosstool_fixtures.py -v`
Expected: FAIL (FileNotFoundError — the fixtures do not exist yet).

- [ ] **Step 3: Create the Jira fixture**

Create `data/captured/crosstool_web_jira.json`:

```json
[
  {"key": "SSSB-1", "status": "In Progress", "team": "Atlas"},
  {"key": "SSSB-2", "status": "Done", "team": "Atlas"},
  {"key": "SSSB-3", "status": "Done", "team": "Boreas"},
  {"key": "SSSB-7", "status": "In Progress", "team": "Cygnus"}
]
```

- [ ] **Step 4: Create the GitHub fixture**

Create `data/captured/crosstool_web_github.json`. Note: SSSB-1 is deliberately absent (no linked work). SSSB-7's only stamp is its open PR `updated_at` (2026-06-08), 17 days before `as_of`, with no commit, so it reads as stalled.

```json
[
  {"type": "pr", "number": 12, "title": "SSSB-2 auth refresh", "state": "open", "merged": false, "url": "https://github.com/davidmjackson/sprintsight-sandbox/pull/12", "updated_at": "2026-06-24T09:00:00Z"},
  {"type": "branch", "name": "feature/SSSB-3-dashboard"},
  {"type": "pr", "number": 5, "title": "SSSB-3 dashboard", "state": "closed", "merged": true, "url": "https://github.com/davidmjackson/sprintsight-sandbox/pull/5", "updated_at": "2026-06-20T09:00:00Z"},
  {"type": "commit", "message": "SSSB-3 ship dashboard", "committed_at": "2026-06-20T08:00:00Z"},
  {"type": "branch", "name": "feature/SSSB-7-export-csv"},
  {"type": "pr", "number": 20, "title": "SSSB-7 export to CSV", "state": "open", "merged": false, "url": "https://github.com/davidmjackson/sprintsight-sandbox/pull/20", "updated_at": "2026-06-08T09:00:00Z"}
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/web/test_crosstool_fixtures.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add data/captured/crosstool_web_jira.json data/captured/crosstool_web_github.json tests/web/test_crosstool_fixtures.py
git commit -m "test(stage7): web-demo cross-tool fixtures (red+amber+green) with reconcile guard [SS-5]"
```

---

### Task 2: Plain-English citation helper (pure)

Create the new module with the pure token-to-prose mapping, tested in isolation before the view function depends on it.

**Files:**
- Create: `sprintsight/web/crosstool_service.py`
- Test: `tests/web/test_crosstool_service.py`

**Interfaces:**
- Produces: `_github_citation(token: str) -> str` and `_jira_citation(key: str, status: str) -> str`, consumed by `crosstool_view` in Task 3. Token grammar comes from `Verdict.signals[0]` emitted by `reconcile`: `github:no-ref:KEY`, `github:no-merged-pr:KEY`, `github:active:KEY`, `github:n/a:KEY`, `github:PR#<n>:open-unmerged`, `github:PR#<n>:stalled-<d>d`.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_crosstool_service.py`:

```python
from sprintsight.web.crosstool_service import _github_citation, _jira_citation


def test_jira_citation_reads_as_prose():
    assert _jira_citation("SSSB-1", "In Progress") == "Jira SSSB-1 (In Progress)"


def test_github_citation_mapping():
    assert _github_citation("github:no-ref:SSSB-1") == (
        "GitHub: no linked branch, PR, or commit"
    )
    assert _github_citation("github:no-merged-pr:SSSB-9") == (
        "GitHub: work exists but nothing merged"
    )
    assert _github_citation("github:active:SSSB-3") == "GitHub: active, linked work found"
    assert _github_citation("github:n/a:SSSB-4") == "GitHub: ticket not claiming progress"
    assert _github_citation("github:PR#12:open-unmerged") == (
        "GitHub: PR #12 is open and unmerged"
    )
    assert _github_citation("github:PR#20:stalled-17d") == (
        "GitHub: PR #20 has had no activity for 17 days"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_crosstool_service.py -v`
Expected: FAIL (ModuleNotFoundError — `crosstool_service` does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `sprintsight/web/crosstool_service.py`:

```python
"""Stage 7 web data layer for the cross-tool watermelon (SS-5).

Reads two captured fixtures (Jira tickets + GitHub items), runs the existing pure
`reconcile()` per ticket against a pinned `as_of`, and shapes the verdicts into view-models
for the `/crosstool` page: a summary band and a flagged-first list with plain-English
citations of BOTH tools. Offline only: no network in a request and no clock, so the page is
deterministic. The burndown world (`service.py`) and every eval gate are untouched.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from sprintsight.connect.github import RecordedGitHubConnector
from sprintsight.crosstool import reconcile
from sprintsight.evals.watermelon import Verdict

CROSSTOOL_AS_OF = "2026-06-25T00:00:00Z"

_DATA = Path(__file__).resolve().parents[2] / "data" / "captured"
_JIRA_FIXTURE = _DATA / "crosstool_web_jira.json"
_GITHUB_FIXTURE = _DATA / "crosstool_web_github.json"


def _jira_citation(key: str, status: str) -> str:
    return f"Jira {key} ({status})"


def _github_citation(token: str) -> str:
    """Turn a `Verdict.signals[0]` token into one readable sentence. Pure."""
    parts = token.split(":")
    kind = parts[1] if len(parts) > 1 else ""
    detail = parts[2] if len(parts) > 2 else ""
    if kind == "no-ref":
        return "GitHub: no linked branch, PR, or commit"
    if kind == "no-merged-pr":
        return "GitHub: work exists but nothing merged"
    if kind == "active":
        return "GitHub: active, linked work found"
    if kind == "n/a":
        return "GitHub: ticket not claiming progress"
    if kind.startswith("PR#"):
        number = kind[3:]
        if detail.startswith("stalled-"):
            days = detail[len("stalled-"):].rstrip("d")
            return f"GitHub: PR #{number} has had no activity for {days} days"
        if detail == "open-unmerged":
            return f"GitHub: PR #{number} is open and unmerged"
    return f"GitHub: {token}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_crosstool_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/crosstool_service.py tests/web/test_crosstool_service.py
git commit -m "feat(stage7): plain-English cross-tool citation helpers [SS-5]"
```

---

### Task 3: View-models + `crosstool_view()` (the served contract)

Add the frozen view-models and the one shaping function. This is the eval-first heart of the slice: served data, not pixels.

**Files:**
- Modify: `sprintsight/web/crosstool_service.py`
- Test: `tests/web/test_crosstool_service.py`

**Interfaces:**
- Consumes: `_github_citation`, `_jira_citation` (Task 2); `reconcile`, `RecordedGitHubConnector` (existing); the Task 1 fixtures.
- Produces: `CrossToolPage(summary: CrossToolSummary, rows: list[CrossToolRow])` and `crosstool_view(as_of: str = CROSSTOOL_AS_OF) -> CrossToolPage`, consumed by the route in Task 4. `CrossToolRow` fields: `key, team, reported_status, actual_status, classification, headline, jira_citation, github_citation`. `classification` is one of `"watermelon" | "stalled" | "clean"`. `CrossToolSummary` fields: `checked, watermelons, stalled, as_of`.

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_crosstool_service.py`:

```python
from sprintsight.web.crosstool_service import crosstool_view

_RANK = {"watermelon": 0, "stalled": 1, "clean": 2}


def test_summary_counts_match_fixtures():
    page = crosstool_view()
    assert page.summary.checked == 4
    assert page.summary.watermelons == 2
    assert page.summary.stalled == 1
    assert page.summary.as_of == "2026-06-25T00:00:00Z"


def test_rows_are_flagged_first():
    classes = [r.classification for r in crosstool_view().rows]
    assert classes == sorted(classes, key=lambda c: _RANK[c])
    assert classes[0] == "watermelon"
    assert classes[-1] == "clean"


def test_each_flagged_row_cites_both_tools():
    flagged = [r for r in crosstool_view().rows if r.classification != "clean"]
    assert flagged
    for r in flagged:
        assert r.jira_citation.startswith("Jira ")
        assert r.github_citation.startswith("GitHub:")


def test_stalled_row_citation_names_the_stalled_pr():
    stalled = [r for r in crosstool_view().rows if r.classification == "stalled"]
    assert len(stalled) == 1
    assert "no activity" in stalled[0].github_citation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_crosstool_service.py -v`
Expected: FAIL (ImportError: cannot import name `crosstool_view`).

- [ ] **Step 3: Write minimal implementation**

Append to `sprintsight/web/crosstool_service.py`:

```python
@dataclass(frozen=True)
class CrossToolSummary:
    checked: int
    watermelons: int
    stalled: int
    as_of: str


@dataclass(frozen=True)
class CrossToolRow:
    key: str
    team: str
    reported_status: str
    actual_status: str
    classification: str  # "watermelon" | "stalled" | "clean"
    headline: str
    jira_citation: str
    github_citation: str


@dataclass(frozen=True)
class CrossToolPage:
    summary: CrossToolSummary
    rows: list[CrossToolRow]


_SORT_RANK = {"watermelon": 0, "stalled": 1, "clean": 2}


def _classification(verdict: Verdict) -> str:
    if verdict.is_watermelon:
        return "watermelon"
    if verdict.actual_status == "amber":
        return "stalled"
    return "clean"


def crosstool_view(as_of: str = CROSSTOOL_AS_OF) -> CrossToolPage:
    """Reconcile every fixture ticket against its GitHub activity and shape the page.

    Pure given the fixtures and `as_of`: the web layer pairs each ticket key with its verdict
    here (a `Verdict` carries no key), so every row keeps its citation.
    """
    tickets = json.loads(_JIRA_FIXTURE.read_text(encoding="utf-8"))
    activity = RecordedGitHubConnector.from_file(_GITHUB_FIXTURE).fetch_activity()
    rows: list[CrossToolRow] = []
    for t in tickets:
        key, status, team = t["key"], t["status"], t.get("team", "")
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
    )
    return CrossToolPage(summary=summary, rows=rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_crosstool_service.py -v`
Expected: PASS (all six tests in the file).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/crosstool_service.py tests/web/test_crosstool_service.py
git commit -m "feat(stage7): crosstool_view shapes the served cross-tool page [SS-5]"
```

---

### Task 4: Route, JSON API, template, and portfolio link

Wire the data layer to FastAPI and render it, reusing the existing shell and design-system CSS. Add the one new badge style.

**Files:**
- Modify: `sprintsight/web/app.py`
- Create: `sprintsight/web/templates/crosstool.html`
- Modify: `sprintsight/web/templates/portfolio.html` (add the nav link)
- Modify: `sprintsight/web/static/app.css` (add `.badge-stalled`)
- Test: `tests/web/test_pages.py`

**Interfaces:**
- Consumes: `crosstool_service.crosstool_view()` and the `CrossToolPage` view-models (Task 3); the `session_user` / `require_api_user` auth seam and `_TEMPLATES` (existing in `app.py`).
- Produces: routes `GET /crosstool` (HTML) and `GET /api/crosstool` (JSON).

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_pages.py`:

```python
def test_crosstool_page_renders_summary_and_flags(client):
    html = client.get("/crosstool").text
    assert "summary-band" in html
    assert "SSSB-1" in html                     # a watermelon ticket
    assert "SSSB-7" in html                     # the stalled ticket
    assert "no activity" in html                # the stalled citation
    assert "Jira SSSB-1" in html                # both tools cited
    assert "GitHub:" in html


def test_crosstool_api_returns_counts(client):
    body = client.get("/api/crosstool").json()
    assert body["summary"]["watermelons"] == 2
    assert body["summary"]["stalled"] == 1
    assert len(body["rows"]) == 4


def test_crosstool_requires_login(anon_client):
    resp = anon_client.get("/crosstool", follow_redirects=False)
    assert resp.status_code == 303              # redirected to /login


def test_portfolio_links_to_crosstool(client):
    assert "/crosstool" in client.get("/").text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_pages.py -k crosstool -v`
Expected: FAIL (404 on `/crosstool` / `/api/crosstool`; no link in portfolio).

- [ ] **Step 3: Add the routes**

In `sprintsight/web/app.py`, add to the imports near the top:

```python
from sprintsight.web import crosstool_service, service
```

(replacing the existing `from sprintsight.web import service` line).

Then add these two routes inside `create_app()`, just after the `api_team` route (keep them above `page_portfolio`):

```python
    @app.get("/api/crosstool")
    def api_crosstool(user: User = Depends(require_api_user)) -> dict:  # noqa: B008
        return asdict(crosstool_service.crosstool_view())

    @app.get("/crosstool", response_class=HTMLResponse)
    def page_crosstool(request: Request) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        page = crosstool_service.crosstool_view()
        return _TEMPLATES.TemplateResponse(
            request, "crosstool.html", {"page": page, "user": user}
        )
```

- [ ] **Step 4: Create the template**

Create `sprintsight/web/templates/crosstool.html`:

```html
{% extends "base.html" %}
{% block title %}Cross-tool signals{% endblock %}
{% block main %}
<h1>Cross-tool signals</h1>
<p class="lede">Jira status versus the actual GitHub activity, per ticket. <a href="/">Back to portfolio</a>.</p>

<div class="summary-band">
  <div class="kpi{% if page.summary.watermelons %} kpi-alert{% endif %}">
    <span class="num">{{ page.summary.watermelons }}</span>
    <span class="label">Watermelons flagged</span>
  </div>
  <div class="kpi">
    <span class="num">{{ page.summary.stalled }}</span>
    <span class="label">Stalled PRs</span>
  </div>
  <div class="kpi">
    <span class="num">{{ page.summary.checked }}</span>
    <span class="label">Tickets checked</span>
  </div>
</div>

<table class="portfolio">
  <thead>
    <tr><th>Ticket</th><th>Team</th><th>Reported</th><th>Actual</th><th>Flag</th><th>Evidence</th></tr>
  </thead>
  <tbody>
  {% for row in page.rows %}
    <tr class="{{ 'watermelon' if row.classification == 'watermelon' else '' }}">
      <td>{{ row.key }}</td>
      <td>{{ row.team }}</td>
      <td><span class="rag rag-{{ row.reported_status }}">{{ row.reported_status }}</span></td>
      <td><span class="rag rag-{{ row.actual_status }}">{{ row.actual_status }}</span></td>
      <td>
        {% if row.classification == 'watermelon' %}
          <span class="badge badge-watermelon" title="Reported healthier than reality">watermelon</span>
        {% elif row.classification == 'stalled' %}
          <span class="badge badge-stalled" title="Open PR has gone quiet">stalled</span>
        {% else %}
          <span class="badge badge-ok">consistent</span>
        {% endif %}
      </td>
      <td class="evidence">{{ row.jira_citation }}<br>{{ row.github_citation }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 5: Add the portfolio nav link**

In `sprintsight/web/templates/portfolio.html`, change the lede line (line 5) to add the link:

```html
<p class="lede">Reported status versus what the data actually shows, as of Sprint {{ summary.sprint }}. <a href="/crosstool">Cross-tool signals (Jira vs GitHub)</a>.</p>
```

- [ ] **Step 6: Add the badge style**

In `sprintsight/web/static/app.css`, add one line after the `.badge-muted` rule:

```css
.badge-stalled { background: #fdf3e3; color: #8a5a00; }
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pytest tests/web/test_pages.py -k crosstool -v`
Expected: PASS (all four crosstool tests).

- [ ] **Step 8: Commit**

```bash
git add sprintsight/web/app.py sprintsight/web/templates/crosstool.html sprintsight/web/templates/portfolio.html sprintsight/web/static/app.css tests/web/test_pages.py
git commit -m "feat(stage7): /crosstool page surfaces cross-tool watermelons + stalled [SS-5]"
```

---

### Task 5: Full suite, lint, docs, and handover

Prove nothing regressed, update the docs of record, and flag the learning queue.

**Files:**
- Modify: `HANDOVER.md`
- Modify: `docs/superpowers/specs/2026-06-25-crosstool-web-ui-design.md` (status line)

- [ ] **Step 1: Run the whole suite**

Run: `pytest -q`
Expected: PASS, with the new tests added and the prior count (216 passed + 3 skipped) increased by the new tests. No failures.

- [ ] **Step 2: Lint**

Run: `ruff check sprintsight tests`
Expected: clean (no errors). Fix any reported issue and re-run.

- [ ] **Step 3: Update HANDOVER.md**

In `HANDOVER.md`, update the "Where we are" / current-state section to record: the `/crosstool` page is built (cross-tool watermelons + amber stalled now visible in the web UI), offline replay only via `data/captured/crosstool_web_*.json`, on branch `stage7-crosstool-web-ui`. If a genuinely new concept arose for a non-engineer, append ONE line to the `Learning queue` section (concept | one line | pointer | 2026-06-25); do not edit LEARNING-LOG.md.

- [ ] **Step 4: Mark the spec delivered**

In `docs/superpowers/specs/2026-06-25-crosstool-web-ui-design.md`, change the Status line to `Status: implemented 2026-06-25 on branch stage7-crosstool-web-ui`.

- [ ] **Step 5: Commit**

```bash
git add HANDOVER.md docs/superpowers/specs/2026-06-25-crosstool-web-ui-design.md
git commit -m "docs(stage7): handover + spec status for the cross-tool web UI slice [SS-5]"
```

---

## Post-plan (owner-driven, not subagent steps)

These mirror the prior slices and are done by the session owner after the plan's tasks pass:

- Code review (general-purpose review subagent), apply non-blocking fixes.
- Create the Jira Story under Epic SS-5, walk Backlog -> ... -> In Review (evals green) -> Done with a completion comment.
- Merge to `main` via `--no-ff`, push, delete the branch.
- Update memory (MEMORY.md + a slice memory file).
```
