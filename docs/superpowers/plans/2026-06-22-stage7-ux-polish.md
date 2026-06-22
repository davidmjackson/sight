# Stage 7 UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the existing Sprintsight web app a demo-ready visual identity ("Direction A — Calm SaaS") across all five screens, adding one new served-data feature (a portfolio summary band) and no new pages or technology.

**Architecture:** Server-rendered FastAPI + Jinja2 + a single hand-written CSS file, exactly as today. The work is overwhelmingly presentation (one CSS rewrite + five template edits). The only non-presentation change is a small, pure, read-only `summarize()` in `service.py` that folds the portfolio rows into headline counts, wired into the existing `/` route.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, plain CSS (no framework, no build step), pytest, Starlette `TestClient`.

## Global Constraints

- No new external calls, no new persisted data, no auth/LLM/cache changes. The slice is presentation + one pure fold over existing data.
- No JavaScript, no front-end build step. Audience tabs stay plain `<a>` links styled as tabs.
- **Preserve these existing class/text hooks** that current tests depend on, so nothing regresses: `rag rag-<status>`, the word `watermelon` on flagged rows, `aud`/`aud-active` on audience links, artifact-id text like `status-atlas-s15`, signal text like `burn ratio`. Restyle them in CSS; do not rename them.
- **New CSS class hooks (introduce and use exactly these names)**: `app-header`, `brand`, `brand-logo`, `summary-band`, `kpi`, `kpi-alert`, `verdict-banner`, `verdict-emoji`, `audience-tabs`, `evidence-card`, `sources-list`.
- Verified seed ground truth: 5 teams (Atlas, Boreas, Cygnus, Draco, Echo); watermelons = 1 (Atlas); insufficient = 1 (Echo); current sprint = 15.
- Run the full suite with `python -m pytest -q` and lint with `ruff check .` from repo root `/var/www/sight`. Both must stay green; deterministic watermelon (4/4) + report (4/4) eval gates are unchanged.
- Commit messages end with the `[SS-5]` tag and the Co-Authored-By trailer for Claude.

---

### Task 1: Portfolio summary (new served data, eval-first)

**Files:**
- Modify: `sprintsight/web/service.py` (add `CURRENT_SPRINT`, `PortfolioSummary`, `summarize`)
- Modify: `sprintsight/web/app.py` (pass `summary` into the `/` route context)
- Test: `tests/web/test_service.py`

**Interfaces:**
- Consumes: existing `TeamRow` (fields `team, reported_status, actual_status, is_watermelon, headline, has_verdict`), existing `portfolio() -> list[TeamRow]`, existing `_SPRINTS = [14, 15]`.
- Produces: `CURRENT_SPRINT: int`; `PortfolioSummary(teams_tracked: int, watermelons: int, insufficient: int, sprint: int)` (frozen dataclass); `summarize(rows: list[TeamRow]) -> PortfolioSummary`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_service.py`:

```python
def _summary_row(team, is_watermelon=False, has_verdict=True):
    return service.TeamRow(
        team=team,
        reported_status="green",
        actual_status="green",
        is_watermelon=is_watermelon,
        headline="",
        has_verdict=has_verdict,
    )


def test_summary_matches_seed_ground_truth():
    s = service.summarize(service.portfolio())
    assert s.teams_tracked == 5
    assert s.watermelons == 1  # Atlas
    assert s.insufficient == 1  # Echo
    assert s.sprint == 15


def test_summary_all_consistent_has_no_watermelons():
    rows = [_summary_row("A"), _summary_row("B")]
    s = service.summarize(rows)
    assert s.watermelons == 0
    assert s.teams_tracked == 2
    assert s.insufficient == 0


def test_summary_counts_insufficient_rows():
    rows = [_summary_row("A", has_verdict=False), _summary_row("B", has_verdict=False)]
    assert service.summarize(rows).insufficient == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_service.py -k summary -v`
Expected: FAIL with `AttributeError: module 'sprintsight.web.service' has no attribute 'summarize'`.

- [ ] **Step 3: Implement `CURRENT_SPRINT`, `PortfolioSummary`, `summarize`**

In `sprintsight/web/service.py`, just below `_SPRINTS = [14, 15]` add:

```python
CURRENT_SPRINT = _SPRINTS[-1]
```

Add this dataclass next to the other view-model dataclasses (e.g. directly above `@dataclass(frozen=True) class TeamRow`):

```python
@dataclass(frozen=True)
class PortfolioSummary:
    teams_tracked: int
    watermelons: int
    insufficient: int
    sprint: int
```

Add this function directly below `def portfolio() -> list[TeamRow]:` (after its `return rows`):

```python
def summarize(rows: list[TeamRow]) -> PortfolioSummary:
    """Fold the portfolio rows into headline counts for the summary band.

    Pure function of rows already in hand: no I/O, so it cannot disagree with the
    table rendered beneath it.
    """
    return PortfolioSummary(
        teams_tracked=len(rows),
        watermelons=sum(1 for r in rows if r.is_watermelon),
        insufficient=sum(1 for r in rows if not r.has_verdict),
        sprint=CURRENT_SPRINT,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_service.py -k summary -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire the summary into the `/` route**

In `sprintsight/web/app.py`, replace the body of `page_portfolio`:

```python
    @app.get("/", response_class=HTMLResponse)
    def page_portfolio(request: Request) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        rows = service.portfolio()
        return _TEMPLATES.TemplateResponse(
            request,
            "portfolio.html",
            {"rows": rows, "summary": service.summarize(rows), "user": user},
        )
```

- [ ] **Step 6: Run the web suite + lint**

Run: `python -m pytest tests/web -q && ruff check sprintsight/web tests/web`
Expected: all green (existing page tests still pass; the template does not yet read `summary`, which is harmless).

- [ ] **Step 7: Commit**

```bash
git add sprintsight/web/service.py sprintsight/web/app.py tests/web/test_service.py
git commit -m "feat(stage7): served portfolio summary counts for the summary band [SS-5]

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Design system (app.css) + top-bar shell (base.html)

**Files:**
- Rewrite: `sprintsight/web/static/app.css`
- Modify: `sprintsight/web/templates/base.html`
- Test: `tests/web/test_pages.py`

**Interfaces:**
- Consumes: the `user` context already passed to every page.
- Produces: the design-system classes named in Global Constraints, available to all templates.

- [ ] **Step 1: Write the failing smoke test**

Append to `tests/web/test_pages.py`:

```python
def test_shell_has_branded_header(client):
    html = client.get("/").text
    assert "app-header" in html
    assert "brand-logo" in html
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/web/test_pages.py::test_shell_has_branded_header -v`
Expected: FAIL (classes not present yet).

- [ ] **Step 3: Rewrite `sprintsight/web/static/app.css`**

Replace the entire file with:

```css
:root {
  /* color tokens */
  --ink: #0f172a;
  --ink-2: #475569;
  --muted: #64748b;
  --faint: #94a3b8;
  --line: #eef0f3;
  --line-2: #e3e6ea;
  --bg: #f7f9fb;
  --surface: #ffffff;
  --accent: #059669;
  --accent-2: #10b981;
  --accent-tint: #ecfdf3;
  --accent-ink: #067647;
  --green: #1a7f37;
  --amber: #bf8700;
  --red: #cf222e;
  --red-tint: #fef6f6;
  --red-line: #fbd5d5;
  --red-ink: #b42318;
  --unknown: #9aa1a9;
  /* scale */
  --radius: 12px;
  --radius-sm: 8px;
  --pad: 18px;
  --shadow: 0 1px 2px rgba(15, 23, 42, .06);
  --shadow-lg: 0 8px 30px rgba(15, 23, 42, .08);
}

* { box-sizing: border-box; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  color: var(--ink);
  background: var(--bg);
  margin: 0;
  line-height: 1.5;
}

/* shell */
.app-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 24px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  font-weight: 700;
  font-size: 15px;
  color: var(--ink);
  text-decoration: none;
}
.brand-logo {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: linear-gradient(135deg, var(--accent-2), var(--accent));
  flex: none;
}
.app-header .sub { color: var(--muted); font-size: 13px; font-weight: 500; }
.session { margin-left: auto; font-size: 13px; color: var(--muted); }
.session a { color: var(--accent); text-decoration: none; }

main { max-width: 920px; margin: 0 auto; padding: 24px; }
h1 { font-size: 1.4rem; margin: 4px 0; }
.lede, .headline { color: var(--muted); margin-top: 0; }
.label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--faint); font-weight: 600; }

/* summary band */
.summary-band { display: flex; gap: 12px; margin: 4px 0 18px; flex-wrap: wrap; }
.kpi {
  flex: 1 1 140px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 12px 16px;
  box-shadow: var(--shadow);
}
.kpi .num { font-size: 22px; font-weight: 700; color: var(--ink); }
.kpi .label { display: block; margin-top: 2px; }
.kpi-alert .num { color: var(--red); }

/* portfolio table */
table.portfolio { width: 100%; border-collapse: collapse; background: var(--surface);
  border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; }
table.portfolio th {
  text-align: left; padding: 10px 14px; font-size: 11px; text-transform: uppercase;
  letter-spacing: .05em; color: var(--faint); border-bottom: 1px solid var(--line);
}
table.portfolio td { text-align: left; padding: 11px 14px; border-bottom: 1px solid var(--line); }
table.portfolio tbody tr:last-child td { border-bottom: none; }
table.portfolio td a { color: var(--ink); text-decoration: none; font-weight: 600; }
table.portfolio td a:hover { color: var(--accent); }
tr.watermelon { background: var(--red-tint); }

/* RAG chips + flag badges (hooks preserved) */
.rag { padding: 2px 9px; border-radius: 999px; font-size: .8rem; color: #fff; text-transform: capitalize; }
.rag-green { background: var(--green); }
.rag-amber { background: var(--amber); }
.rag-red { background: var(--red); }
.rag-unknown { background: var(--unknown); }
.badge { padding: 2px 9px; border-radius: 6px; font-size: .78rem; font-weight: 600; }
.badge-watermelon { background: #fde8e8; color: var(--red-ink); }
.badge-ok { background: var(--accent-tint); color: var(--accent-ink); }
.badge-muted { background: #f2f4f7; color: var(--muted); }

/* team drill-in */
.back { font-size: 13px; color: var(--accent); text-decoration: none; }
.verdict-banner {
  display: flex; gap: 14px; align-items: center; margin: 14px 0 6px;
  padding: 16px 18px; border-radius: var(--radius);
  background: var(--red-tint); border: 1px solid var(--red-line);
}
.verdict-emoji { font-size: 26px; line-height: 1; }
.verdict-banner h1 { margin: 0; }
.verdict-banner .sub { margin: 4px 0 0; color: var(--ink-2); font-size: 14px; }
section.detail h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--faint); margin: 22px 0 8px; }
.explanation { margin: 0; }
ul.signals { margin: 6px 0; padding-left: 18px; }
ul.signals li { margin: 4px 0; }

/* evidence + sources as cited cards */
ul.evidence { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.evidence-card { border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 10px 12px; background: var(--surface); }
.evidence-card strong { font-size: 13px; }
.snippet { color: var(--muted); font-size: .9rem; margin-top: 4px; }
code { background: #f1f5f9; color: var(--ink-2); padding: 1px 6px; border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }

/* audience tabs (hooks aud / aud-active preserved) */
.audience-tabs.audience-switch { display: inline-flex; gap: 4px; background: #f1f5f9;
  padding: 4px; border-radius: var(--radius-sm); margin: 6px 0 14px; }
.audience-switch .aud {
  display: inline-block; padding: 6px 14px; border-radius: 7px;
  font-size: 13px; font-weight: 600; color: var(--ink-2); text-decoration: none;
  border: none; margin: 0;
}
.audience-switch .aud-active { background: var(--surface); color: var(--ink); box-shadow: var(--shadow); }
.report-body { white-space: pre-wrap; margin: 0 0 8px; }
h3 { margin: 14px 0 4px; font-size: 14px; }
.sources-list { border-top: 1px solid var(--line); margin-top: 16px; padding-top: 12px; }
ul.sources { list-style: none; padding: 0; margin: 0; color: var(--ink-2); font-size: 13px; }
ul.sources li { margin: 4px 0; }

/* login + accounts */
.login { max-width: 22rem; margin: 3rem auto; background: var(--surface);
  border: 1px solid var(--line); border-radius: var(--radius); padding: 24px; box-shadow: var(--shadow); }
.login h1 { margin-top: 0; }
.login-form label { display: block; margin: 0.75rem 0; font-size: 13px; color: var(--ink-2); }
.login-form input { width: 100%; padding: 0.5rem; margin-top: 4px; border: 1px solid var(--line-2);
  border-radius: var(--radius-sm); font-size: 14px; }
.login-form button, .accounts button {
  background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm);
  padding: 9px 16px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 8px;
}
.error { color: var(--red); font-size: 13px; }
section.accounts { background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 20px 22px; }
section.accounts table { width: 100%; border-collapse: collapse; }
section.accounts th { text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase;
  letter-spacing: .05em; color: var(--faint); border-bottom: 1px solid var(--line); }
section.accounts td { padding: 9px 10px; border-bottom: 1px solid var(--line); font-size: 14px; }
section.accounts .sub { color: var(--muted); font-size: 13px; }
```

- [ ] **Step 4: Update `sprintsight/web/templates/base.html`**

Replace the `<body>` block with the branded shell:

```html
<body>
  <header class="app-header">
    <a href="/" class="brand"><span class="brand-logo"></span>Sprintsight</a>
    <span class="sub">watermelon detector</span>
    <span class="session">
      {% if user %}{{ user.email }} ({{ user.role }}) &middot; <a href="/logout">Sign out</a>
      {% else %}<a href="/login">Sign in</a>{% endif %}
    </span>
  </header>
  <main>{% block main %}{% endblock %}</main>
</body>
```

(Leave the `<head>` block unchanged.)

- [ ] **Step 5: Run the smoke test + full web suite**

Run: `python -m pytest tests/web -q`
Expected: all pass, including `test_shell_has_branded_header`.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/web/static/app.css sprintsight/web/templates/base.html tests/web/test_pages.py
git commit -m "feat(stage7): design-system CSS + branded top-bar shell [SS-5]

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Portfolio summary band + table restyle (portfolio.html)

**Files:**
- Modify: `sprintsight/web/templates/portfolio.html`
- Test: `tests/web/test_pages.py`

**Interfaces:**
- Consumes: `summary` (a `PortfolioSummary`) and `rows` (list of `TeamRow`) from the `/` route.

- [ ] **Step 1: Write the failing smoke test**

Append to `tests/web/test_pages.py`:

```python
def test_portfolio_page_shows_summary_band(client):
    html = client.get("/").text
    assert "summary-band" in html
    assert "Watermelon" in html  # KPI label
    assert "Teams tracked" in html
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/web/test_pages.py::test_portfolio_page_shows_summary_band -v`
Expected: FAIL (band not rendered yet).

- [ ] **Step 3: Update `sprintsight/web/templates/portfolio.html`**

Replace the file with:

```html
{% extends "base.html" %}
{% block title %}Portfolio{% endblock %}
{% block main %}
<h1>Team portfolio</h1>
<p class="lede">Reported status versus what the data actually shows, as of Sprint {{ summary.sprint }}.</p>

<div class="summary-band">
  <div class="kpi kpi-alert">
    <span class="num">{{ summary.watermelons }}</span>
    <span class="label">Watermelons flagged</span>
  </div>
  <div class="kpi">
    <span class="num">{{ summary.teams_tracked }}</span>
    <span class="label">Teams tracked</span>
  </div>
  <div class="kpi">
    <span class="num">{{ summary.insufficient }}</span>
    <span class="label">Insufficient evidence</span>
  </div>
  <div class="kpi">
    <span class="num">{{ summary.sprint }}</span>
    <span class="label">Current sprint</span>
  </div>
</div>

<table class="portfolio">
  <thead>
    <tr><th>Team</th><th>Reported</th><th>Actual</th><th>Flag</th></tr>
  </thead>
  <tbody>
  {% for row in rows %}
    <tr class="{{ 'watermelon' if row.is_watermelon else '' }}">
      <td><a href="/team/{{ row.team|lower }}">{{ row.team }}</a></td>
      <td><span class="rag rag-{{ row.reported_status }}">{{ row.reported_status }}</span></td>
      <td><span class="rag rag-{{ row.actual_status }}">{{ row.actual_status }}</span></td>
      <td>
        {% if not row.has_verdict %}
          <span class="badge badge-muted">insufficient evidence</span>
        {% elif row.is_watermelon %}
          <span class="badge badge-watermelon" title="Reported healthier than reality">watermelon</span>
        {% else %}
          <span class="badge badge-ok">consistent</span>
        {% endif %}
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 4: Run the smoke test + full web suite**

Run: `python -m pytest tests/web -q`
Expected: all pass (the new band test plus the existing portfolio tests).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/templates/portfolio.html tests/web/test_pages.py
git commit -m "feat(stage7): portfolio summary band + table restyle [SS-5]

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Team drill-in polish — verdict banner, tabs, cited cards (team.html)

**Files:**
- Modify: `sprintsight/web/templates/team.html`
- Test: `tests/web/test_pages.py`

**Interfaces:**
- Consumes: `d` (a `TeamDetail`) from the `/team/{team_id}` route. Fields used: `team, has_verdict, is_watermelon, reported_status, actual_status, headline, explanation, signals, evidence` (each `EvidenceItem` has `title, artifact_id, snippet`), `audience, report_insufficient, report_sections` (each `ReportSection` has `heading, body`), `report_sources`.

- [ ] **Step 1: Write the failing smoke test**

Append to `tests/web/test_pages.py`:

```python
def test_team_page_atlas_has_verdict_banner(client):
    html = client.get("/team/atlas").text
    assert "verdict-banner" in html
    assert "verdict-emoji" in html


def test_team_page_audience_tabs_present(client):
    html = client.get("/team/atlas").text
    assert "audience-tabs" in html
    assert html.count('class="aud') >= 3  # three audience tabs
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/web/test_pages.py -k "verdict_banner or audience_tabs" -v`
Expected: FAIL (`verdict-banner` / `audience-tabs` not present yet).

- [ ] **Step 3: Update `sprintsight/web/templates/team.html`**

Replace the file with:

```html
{% extends "base.html" %}
{% block title %}{{ d.team }}{% endblock %}
{% block main %}
<p><a href="/" class="back">&larr; Back to portfolio</a></p>

{% if d.has_verdict and d.is_watermelon %}
<div class="verdict-banner">
  <span class="verdict-emoji">🍉</span>
  <div>
    <h1>{{ d.team }} <span class="badge badge-watermelon">watermelon</span></h1>
    <p class="sub">
      Reported <span class="rag rag-{{ d.reported_status }}">{{ d.reported_status }}</span>
      but computed actual <span class="rag rag-{{ d.actual_status }}">{{ d.actual_status }}</span>.
      The status looks healthier than the data supports.
    </p>
  </div>
</div>
{% else %}
<h1>{{ d.team }}</h1>
<p class="headline">{{ d.headline }}</p>
{% endif %}

<section class="detail">
{% if d.has_verdict %}
{% if not d.is_watermelon %}
<p>
  Reported <span class="rag rag-{{ d.reported_status }}">{{ d.reported_status }}</span>,
  computed actual <span class="rag rag-{{ d.actual_status }}">{{ d.actual_status }}</span>.
</p>
{% endif %}

<h2>Why</h2>
<p class="explanation">{{ d.explanation }}</p>

<h2>Signals</h2>
<ul class="signals">
  {% for s in d.signals %}<li>{{ s }}</li>{% endfor %}
</ul>

<h2>Evidence</h2>
<ul class="evidence">
  {% for e in d.evidence %}
    <li class="evidence-card">
      <strong>{{ e.title }}</strong>
      <code>{{ e.artifact_id }}</code>
      {% if e.snippet %}<div class="snippet">{{ e.snippet }}</div>{% endif %}
    </li>
  {% endfor %}
</ul>

<h2>Status report</h2>
<p class="audience-tabs audience-switch">
  {% for a in ["exec", "programme", "team"] %}
    <a href="/team/{{ d.team|lower }}?audience={{ a }}"
       class="aud{% if d.audience == a %} aud-active{% endif %}">{{ a|capitalize }}</a>
  {% endfor %}
</p>
{% if d.report_insufficient %}
  <p class="explanation">Not enough evidence to write a report.</p>
{% else %}
  {% for s in d.report_sections %}
    <h3>{{ s.heading }}</h3>
    <p class="report-body">{{ s.body }}</p>
  {% endfor %}
  {% if d.report_sources %}
  <div class="sources-list">
    <h3>Sources</h3>
    <ul class="sources">
      {% for src in d.report_sources %}
        <li><strong>{{ src.title }}</strong> <code>{{ src.artifact_id }}</code></li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}
{% endif %}
{% else %}
<p class="explanation">{{ d.explanation }}</p>
{% endif %}
</section>
{% endblock %}
```

- [ ] **Step 4: Run the smoke tests + full web suite**

Run: `python -m pytest tests/web -q`
Expected: all pass, including the new banner/tabs tests and the existing team-page tests (`status-atlas-s15`, `burn ratio`, audience switch, report visible).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/templates/team.html tests/web/test_pages.py
git commit -m "feat(stage7): team drill-in verdict banner, audience tabs, cited cards [SS-5]

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Login + admin consistency pass (login.html, admin_accounts.html)

**Files:**
- Modify: `sprintsight/web/templates/login.html`
- Modify: `sprintsight/web/templates/admin_accounts.html`
- Test: `tests/web/test_pages.py`

**Interfaces:**
- Consumes: existing `error` (login) and `accounts` (admin) context. No new data.

- [ ] **Step 1: Write the failing smoke test**

Append to `tests/web/test_pages.py`:

```python
def test_login_page_uses_shell(anon_client):
    html = anon_client.get("/login").text
    assert "app-header" in html  # inherits the branded shell
    assert "brand-logo" in html


def test_admin_accounts_uses_shell(client):
    html = client.get("/admin/accounts").text
    assert "app-header" in html
    assert "Accounts" in html
```

- [ ] **Step 2: Run them to verify they pass-or-fail**

Run: `python -m pytest tests/web/test_pages.py -k "login_page_uses_shell or admin_accounts_uses_shell" -v`
Expected: PASS already for the `app-header` parts (both templates extend `base.html`, updated in Task 2). This task confirms they still render correctly after the light restyle and locks the assertion. If they pass at this step, proceed to Step 3 to apply the cosmetic pass and keep them green.

- [ ] **Step 3: Update `sprintsight/web/templates/login.html`**

Replace the file with (adds a one-line lede; structure and field names unchanged):

```html
{% extends "base.html" %}
{% block title %}Sign in - Sprintsight{% endblock %}
{% block main %}
<section class="login">
  <h1>Sign in</h1>
  <p class="lede">Sign in to view the team portfolio.</p>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post" action="/login" class="login-form">
    <label>Email
      <input type="email" name="email" autocomplete="username" required>
    </label>
    <label>Password
      <input type="password" name="password" autocomplete="current-password" required>
    </label>
    <button type="submit">Sign in</button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 4: Update `sprintsight/web/templates/admin_accounts.html`**

Replace the file with (adds the back link for consistency with the team page; table now picks up `section.accounts` styling):

```html
{% extends "base.html" %}
{% block title %}Accounts - Sprintsight{% endblock %}
{% block main %}
<p><a href="/" class="back">&larr; Back to portfolio</a></p>
<section class="accounts">
  <h1>Accounts</h1>
  <p class="sub">Admin only. Synthetic demo users.</p>
  <table>
    <thead><tr><th>Email</th><th>Role</th></tr></thead>
    <tbody>
      {% for a in accounts %}
      <tr><td>{{ a.email }}</td><td>{{ a.role }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 5: Run the full suite + lint**

Run: `python -m pytest -q && ruff check .`
Expected: full suite green (was 174 passed + 3 skipped before this slice, now higher with the added tests), ruff clean.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/web/templates/login.html sprintsight/web/templates/admin_accounts.html tests/web/test_pages.py
git commit -m "feat(stage7): login + admin consistency pass on the new shell [SS-5]

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Close-out — HANDOVER, learning flag, eval gates

**Files:**
- Modify: `HANDOVER.md`

- [ ] **Step 1: Confirm eval gates unchanged and green**

Run: `python -m pytest -q`
Expected: full suite green; deterministic watermelon (4/4) + report (4/4) eval tests pass exactly as before.

- [ ] **Step 2: Update `HANDOVER.md`**

In the "Where we are" section, add a short paragraph: Stage 7 first slice (UX Polish, Epic SS-5) done on branch `stage7-ux-polish`; demo-ready Direction-A visual identity across all five screens; new served data = portfolio summary counts (5 teams, 1 watermelon, 1 insufficient, sprint 15); pure presentation otherwise; connectors deferred to the second Stage 7 slice.

Append one line to the `Learning queue` section:

```
- A design system / design tokens | the app's look now lives in named CSS variables (one place to change a color or spacing) instead of being repeated across templates; this is what makes a UI consistent and quick to restyle | sprintsight/web/static/app.css :root tokens + stage7-ux-polish slice | flagged 2026-06-22
```

- [ ] **Step 3: Commit**

```bash
git add HANDOVER.md
git commit -m "docs(stage7): HANDOVER + learning-queue flag for UX-polish slice [SS-5]

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- After all tasks: this is a good point for a whole-branch review before merging to `main`. The merge itself and the Jira SS-5 slice-Story transitions (Backlog → To Do → In Progress → In Review → Done + completion comment) are owned by the driving session, not this plan.
- Manual visual verification in a browser is optional and not part of CI (it is presentation; the tests assert structure + served data, not pixels).
