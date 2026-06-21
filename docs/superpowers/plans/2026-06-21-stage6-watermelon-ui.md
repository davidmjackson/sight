# Stage 6 Watermelon UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the project's first screen: a FastAPI web app with a portfolio grid of all teams (reported vs computed RAG + watermelon badge) and a per-team drill-in showing the signals and evidence behind the flag.

**Architecture:** One Python FastAPI app (Option A from the spec). A pure data layer (`sprintsight/web/service.py`) reads the synthetic corpus through the existing detector path (`graph_detector()`) and shapes view-models. FastAPI routes render those view-models as both JSON (`/api/*`) and server-rendered Jinja2 HTML. No JavaScript, no database, no LLM, no auth. Corpus-driven and fully offline.

**Tech Stack:** Python 3.11, FastAPI, Jinja2, Starlette `TestClient` (httpx), pytest, ruff. The detector/graph/fixtures layers already exist and are reused unchanged except for one additive field.

## Global Constraints

- Python >= 3.11; frozen dataclasses for view-models.
- Fully offline: no `ANTHROPIC_API_KEY`, no network, no database. The default detector path (`graph_detector()`) uses the in-memory retriever + hashing embedder and is offline-safe.
- Reuse the existing detector; do not re-implement detection logic. The only change to existing code is adding one optional, backward-compatible field to `Verdict`.
- No em dashes in any user-visible copy (templates, headlines, strings the user reads). Use commas, periods, or parentheses.
- ruff must stay clean: `select = ["E", "F", "I", "UP", "B"]`, line-length 100.
- The portfolio judges as-of Sprint 15 with Sprint 14 as context. Expected verdicts are the Sprint-15 blocks in `data/ground-truth/labels.yaml`.
- Teams shown: Atlas, Boreas, Cygnus, Draco, Echo. Echo is thin-data and must render as "insufficient evidence", never a crash and never a flag.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Work happens on the existing `stage6-watermelon-ui` branch.
- The deterministic watermelon + report evals remain the CI gate and must stay green.

---

### Task 1: Dependencies, CI, and package skeleton

**Files:**
- Modify: `pyproject.toml` (add `web` optional extra)
- Modify: `.github/workflows/ci.yml` (install `.[dev,web]` in the lint-and-test job)
- Create: `sprintsight/web/__init__.py`
- Create: `tests/web/__init__.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable `sprintsight.web` package and the `web` extra so later tasks can import FastAPI/Jinja2/httpx.

- [ ] **Step 1: Add the `web` extra to `pyproject.toml`**

In `[project.optional-dependencies]`, add (keep the existing `dev`, `eval`, `db` groups):

```toml
# Stage 6 web app (FastAPI portfolio + watermelon drill-in). httpx is the test client;
# uvicorn runs the server locally and is not needed for the tests.
web = [
  "fastapi>=0.110",
  "jinja2>=3",
  "httpx>=0.27",
  "uvicorn>=0.30",
]
```

- [ ] **Step 2: Point CI's lint-and-test job at the web extra**

In `.github/workflows/ci.yml`, the `lint-and-test` job currently runs (line 20):

```yaml
          pip install -e ".[dev,eval]"
```

Change it to add `web`:

```yaml
          pip install -e ".[dev,eval,web]"
```

Leave the `db` job's `pip install -e ".[db]"` (line 60) untouched.

- [ ] **Step 3: Create the package and test-package markers**

`sprintsight/web/__init__.py`:

```python
"""Stage 6 web app (SS-6): portfolio + watermelon drill-in."""
```

`tests/web/__init__.py`:

```python
```

- [ ] **Step 4: ASK DAVID to install the web extra (do not run it yourself)**

Per David's instruction, the install is run by him. Present exactly this one command, fenced, and wait for its output before continuing:

```bash
cd /var/www/sight && .venv/bin/pip install -e ".[dev,web]"
```

Expected: a successful install listing fastapi, starlette, jinja2, httpx, uvicorn.

- [ ] **Step 5: Verify the package imports and deps are present**

Run: `.venv/bin/python -c "import fastapi, jinja2, httpx; import sprintsight.web; print('ok')"`
Expected: prints `ok` with no ImportError.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .github/workflows/ci.yml sprintsight/web/__init__.py tests/web/__init__.py
git commit -m "$(printf 'chore(stage6): add web extra + package skeleton [SS-6]\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Expose structured `signals` on `Verdict`

The drill-in shows the signals (burn ratio, velocity decline, hidden dependency) as bullets. The detector already computes these as a local `signals` list but only joins them into `explanation`. Expose them as a first-class, backward-compatible field so the UI does not have to parse prose.

**Files:**
- Modify: `sprintsight/evals/watermelon.py` (add field to `Verdict`)
- Modify: `sprintsight/detector.py` (pass `signals` into the returned `Verdict`)
- Test: `tests/web/test_detector_signals.py`

**Interfaces:**
- Consumes: `detect(inputs: dict) -> Verdict` from `sprintsight/detector.py`; `artifacts_for(team, sprints)` from `sprintsight/evals/fixtures.py`.
- Produces: `Verdict.signals: list[str]` (defaults to `[]`), populated by `detect()`.

- [ ] **Step 1: Write the failing test**

`tests/web/test_detector_signals.py`:

```python
from sprintsight.detector import detect
from sprintsight.evals.fixtures import artifacts_for


def test_detect_exposes_signals_for_atlas():
    arts = artifacts_for("Atlas", [14, 15])
    verdict = detect({"team": "Atlas", "artifacts": arts})
    assert isinstance(verdict.signals, list)
    assert verdict.signals, "expected non-empty signals"
    assert any("burn ratio" in s for s in verdict.signals)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/web/test_detector_signals.py -v`
Expected: FAIL with `AttributeError: 'Verdict' object has no attribute 'signals'`.

- [ ] **Step 3: Add the field to `Verdict`**

In `sprintsight/evals/watermelon.py`, in the `Verdict` dataclass, add a `signals` field after `evidence` (it already imports `field`):

```python
    evidence: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    explanation: str = ""
```

- [ ] **Step 4: Populate `signals` in `detect()`**

In `sprintsight/detector.py`, in the `return Verdict(...)` at the end of `detect()`, add `signals=signals,` (the local `signals` list already exists):

```python
    return Verdict(
        team=team,
        reported_status=reported,
        actual_status=actual,
        is_watermelon=is_watermelon,
        evidence=evidence,
        signals=signals,
        explanation=explanation,
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/web/test_detector_signals.py -v`
Expected: PASS.

- [ ] **Step 6: Confirm the watermelon eval is still 4/4 (no regression)**

Run: `.venv/bin/python scripts/run_watermelon_eval.py`
Expected: classification 4/4 and evidence 4/4, exit 0.

- [ ] **Step 7: Commit**

```bash
git add sprintsight/evals/watermelon.py sprintsight/detector.py tests/web/test_detector_signals.py
git commit -m "$(printf 'feat(stage6): expose structured signals on Verdict [SS-6]\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: The data layer (`service.py`) — the eval-first gate

**Files:**
- Create: `sprintsight/web/service.py`
- Test: `tests/web/test_service.py`

**Interfaces:**
- Consumes: `artifacts_for(team, sprints)` and `Artifact` from `sprintsight/evals/fixtures.py`; `Verdict` from `sprintsight/evals/watermelon.py`; `graph_detector()` from `sprintsight/graph/builder.py`.
- Produces:
  - `TEAMS: list[str]` = `["Atlas", "Boreas", "Cygnus", "Draco", "Echo"]`
  - `EvidenceItem(artifact_id, source_type, sprint, title, snippet)` frozen dataclass
  - `TeamRow(team, reported_status, actual_status, is_watermelon, headline, has_verdict)` frozen dataclass
  - `TeamDetail(team, reported_status, actual_status, is_watermelon, headline, has_verdict, signals, explanation, evidence)` frozen dataclass
  - `portfolio() -> list[TeamRow]`
  - `team_detail(team_id: str) -> TeamDetail | None` (None when the team id is unknown)

- [ ] **Step 1: Write the failing tests**

`tests/web/test_service.py`:

```python
from sprintsight.web import service


def _row(rows, team):
    return next(r for r in rows if r.team == team)


def test_portfolio_returns_all_teams():
    rows = service.portfolio()
    assert {r.team for r in rows} == {"Atlas", "Boreas", "Cygnus", "Draco", "Echo"}


def test_atlas_is_watermelon_red():
    atlas = _row(service.portfolio(), "Atlas")
    assert atlas.has_verdict is True
    assert atlas.is_watermelon is True
    assert atlas.reported_status == "green"
    assert atlas.actual_status == "red"


def test_boreas_green_not_watermelon():
    boreas = _row(service.portfolio(), "Boreas")
    assert boreas.is_watermelon is False
    assert boreas.actual_status == "green"


def test_cygnus_amber_not_watermelon():
    cygnus = _row(service.portfolio(), "Cygnus")
    assert cygnus.is_watermelon is False
    assert cygnus.actual_status == "amber"


def test_draco_amber_not_watermelon():
    draco = _row(service.portfolio(), "Draco")
    assert draco.is_watermelon is False
    assert draco.actual_status == "amber"


def test_echo_insufficient_evidence():
    echo = _row(service.portfolio(), "Echo")
    assert echo.has_verdict is False
    assert echo.is_watermelon is False


def test_team_detail_atlas_evidence_and_signals():
    detail = service.team_detail("atlas")
    assert detail is not None
    assert detail.is_watermelon is True
    ids = {e.artifact_id for e in detail.evidence}
    assert "status-atlas-s15" in ids
    assert "burndown-atlas-s15" in ids
    assert "slack-atlas-s15-msg-dep" in ids
    assert detail.signals, "expected non-empty signals"
    assert any("burn ratio" in s for s in detail.signals)


def test_team_detail_unknown_returns_none():
    assert service.team_detail("nope") is None


def test_team_detail_echo_insufficient():
    detail = service.team_detail("echo")
    assert detail is not None
    assert detail.has_verdict is False
    assert detail.evidence == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/web/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.web.service'`.

- [ ] **Step 3: Write `service.py`**

`sprintsight/web/service.py`:

```python
"""Stage 6 web data layer (SS-6).

Reads the synthetic corpus through the existing detector path and shapes view-models for
the portfolio grid and the per-team drill-in. Pure Python: no HTTP, no LLM, no database.
The detector sits behind this seam so a future DB-backed detector can replace it without
touching the pages. The portfolio judges as-of Sprint 15 with Sprint 14 as context.
"""

from dataclasses import dataclass, field

from sprintsight.evals.fixtures import Artifact, artifacts_for
from sprintsight.evals.watermelon import Verdict
from sprintsight.graph.builder import graph_detector

TEAMS: list[str] = ["Atlas", "Boreas", "Cygnus", "Draco", "Echo"]
_SPRINTS = [14, 15]

_SOURCE_LABELS = {
    "status": "Status report",
    "burndown": "Burndown",
    "raid": "RAID log",
    "slack": "Chat message",
    "chat": "Chat message",
    "jira": "Jira ticket",
    "triage": "Triage note",
    "bugspike": "Bug spike",
}

_detector = graph_detector()


@dataclass(frozen=True)
class EvidenceItem:
    artifact_id: str
    source_type: str
    sprint: int
    title: str
    snippet: str


@dataclass(frozen=True)
class TeamRow:
    team: str
    reported_status: str
    actual_status: str
    is_watermelon: bool
    headline: str
    has_verdict: bool


@dataclass(frozen=True)
class TeamDetail:
    team: str
    reported_status: str
    actual_status: str
    is_watermelon: bool
    headline: str
    has_verdict: bool
    signals: list[str] = field(default_factory=list)
    explanation: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)


def portfolio() -> list[TeamRow]:
    rows: list[TeamRow] = []
    for team in TEAMS:
        verdict = _verdict_or_none(team)
        if verdict is None:
            rows.append(_insufficient_row(team))
            continue
        rows.append(
            TeamRow(
                team=team,
                reported_status=verdict.reported_status,
                actual_status=verdict.actual_status,
                is_watermelon=verdict.is_watermelon,
                headline=_headline(verdict),
                has_verdict=True,
            )
        )
    return rows


def team_detail(team_id: str) -> TeamDetail | None:
    team = _resolve_team(team_id)
    if team is None:
        return None
    verdict = _verdict_or_none(team)
    if verdict is None:
        return _insufficient_detail(team)
    arts = artifacts_for(team, _SPRINTS)
    return TeamDetail(
        team=team,
        reported_status=verdict.reported_status,
        actual_status=verdict.actual_status,
        is_watermelon=verdict.is_watermelon,
        headline=_headline(verdict),
        has_verdict=True,
        signals=list(verdict.signals),
        explanation=verdict.explanation,
        evidence=[_evidence_item(aid, arts) for aid in verdict.evidence],
    )


def _verdict_or_none(team: str) -> Verdict | None:
    """Run the detector, or return None when the team has too little data to judge."""
    arts = artifacts_for(team, _SPRINTS)
    if not _has_minimum(team, arts):
        return None
    try:
        return _detector({"team": team, "artifacts": arts})
    except Exception:
        return None


def _has_minimum(team: str, arts: dict[str, Artifact]) -> bool:
    t = team.lower()
    return f"status-{t}-s15" in arts and f"burndown-{t}-s15" in arts


def _resolve_team(team_id: str) -> str | None:
    for team in TEAMS:
        if team.lower() == team_id.lower():
            return team
    return None


def _headline(verdict: Verdict) -> str:
    base = f"Reported {verdict.reported_status}, computed {verdict.actual_status}"
    if verdict.is_watermelon:
        return f"{base} (looks healthier than it is)."
    return f"{base} (consistent)."


def _evidence_item(artifact_id: str, arts: dict[str, Artifact]) -> EvidenceItem:
    art = arts.get(artifact_id)
    if art is None:
        return EvidenceItem(artifact_id, "unknown", 0, artifact_id, "")
    label = _SOURCE_LABELS.get(art.source_type, art.source_type.title() or "Artifact")
    snippet = art.body.strip().splitlines()[0][:200] if art.body.strip() else ""
    return EvidenceItem(
        artifact_id=art.artifact_id,
        source_type=art.source_type,
        sprint=art.sprint,
        title=f"{label} (Sprint {art.sprint})",
        snippet=snippet,
    )


def _insufficient_row(team: str) -> TeamRow:
    return TeamRow(
        team=team,
        reported_status="unknown",
        actual_status="unknown",
        is_watermelon=False,
        headline="Insufficient evidence to judge this team.",
        has_verdict=False,
    )


def _insufficient_detail(team: str) -> TeamDetail:
    return TeamDetail(
        team=team,
        reported_status="unknown",
        actual_status="unknown",
        is_watermelon=False,
        headline="Insufficient evidence to judge this team.",
        has_verdict=False,
        signals=[],
        explanation="This team has too little Sprint 15 data (no burndown or status) to judge.",
        evidence=[],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/web/test_service.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check sprintsight/web/service.py tests/web/test_service.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/web/service.py tests/web/test_service.py
git commit -m "$(printf 'feat(stage6): web data layer (portfolio + team_detail) green vs ground truth [SS-6]\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: The JSON API (`app.py` + `/api/*` routes)

**Files:**
- Create: `sprintsight/web/app.py`
- Test: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `service.portfolio()`, `service.team_detail()`, and the view-model dataclasses from Task 3.
- Produces:
  - `create_app() -> FastAPI`
  - module-level `app = create_app()` (so `uvicorn sprintsight.web.app:app` works)
  - `GET /api/portfolio` -> `list[dict]`; `GET /api/team/{team_id}` -> `dict` (404 on unknown team)

- [ ] **Step 1: Write the failing tests**

`tests/web/test_api.py`:

```python
from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

client = TestClient(create_app())


def test_api_portfolio_verdicts():
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    rows = {row["team"]: row for row in resp.json()}
    assert rows["Atlas"]["is_watermelon"] is True
    assert rows["Atlas"]["actual_status"] == "red"
    assert rows["Boreas"]["is_watermelon"] is False
    assert rows["Echo"]["has_verdict"] is False


def test_api_team_atlas_detail():
    resp = client.get("/api/team/atlas")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_watermelon"] is True
    ids = {e["artifact_id"] for e in body["evidence"]}
    assert "slack-atlas-s15-msg-dep" in ids
    assert body["signals"]


def test_api_team_unknown_404():
    assert client.get("/api/team/nope").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/web/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.web.app'`.

- [ ] **Step 3: Write `app.py` (API routes only for now)**

`sprintsight/web/app.py`:

```python
"""Stage 6 FastAPI app (SS-6): portfolio grid + per-team watermelon drill-in."""

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sprintsight.web import service

_HERE = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="Sprintsight watermelon detector")
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    @app.get("/api/portfolio")
    def api_portfolio() -> list[dict]:
        return [asdict(row) for row in service.portfolio()]

    @app.get("/api/team/{team_id}")
    def api_team(team_id: str) -> dict:
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return asdict(detail)

    @app.get("/", response_class=HTMLResponse)
    def page_portfolio(request: Request) -> HTMLResponse:
        return _TEMPLATES.TemplateResponse(
            "portfolio.html", {"request": request, "rows": service.portfolio()}
        )

    @app.get("/team/{team_id}", response_class=HTMLResponse)
    def page_team(request: Request, team_id: str) -> HTMLResponse:
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return _TEMPLATES.TemplateResponse("team.html", {"request": request, "d": detail})

    return app


app = create_app()
```

Note: the `/` and `/team/{id}` HTML routes reference templates created in Task 5. The API tests in this task do not hit them, so they pass now; the static mount requires the directory to exist, so create it in this step.

- [ ] **Step 4: Create the static directory with a placeholder so the mount resolves**

Create `sprintsight/web/static/app.css` (filled in Task 5):

```css
/* Stage 6 styles (filled in Task 5). */
```

- [ ] **Step 5: Run the API tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/web/test_api.py -v`
Expected: all PASS.

- [ ] **Step 6: Lint**

Run: `.venv/bin/ruff check sprintsight/web/app.py tests/web/test_api.py`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add sprintsight/web/app.py sprintsight/web/static/app.css tests/web/test_api.py
git commit -m "$(printf 'feat(stage6): JSON API (/api/portfolio, /api/team) over the data layer [SS-6]\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: The HTML pages (templates + styling + smoke tests)

**Files:**
- Create: `sprintsight/web/templates/base.html`
- Create: `sprintsight/web/templates/portfolio.html`
- Create: `sprintsight/web/templates/team.html`
- Modify: `sprintsight/web/static/app.css`
- Test: `tests/web/test_pages.py`

**Interfaces:**
- Consumes: the HTML routes from Task 4 (`/`, `/team/{id}`) and the view-models (`rows` is `list[TeamRow]`; `d` is `TeamDetail`).
- Produces: rendered HTML for the portfolio grid and the drill-in.

- [ ] **Step 1: Write the failing smoke tests**

`tests/web/test_pages.py`:

```python
from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

client = TestClient(create_app())


def test_portfolio_page_lists_all_teams():
    resp = client.get("/")
    assert resp.status_code == 200
    for team in ("Atlas", "Boreas", "Cygnus", "Draco", "Echo"):
        assert team in resp.text


def test_portfolio_page_flags_atlas():
    resp = client.get("/")
    assert "watermelon" in resp.text.lower()


def test_team_page_atlas_shows_evidence_and_signals():
    resp = client.get("/team/atlas")
    assert resp.status_code == 200
    assert "red" in resp.text.lower()
    assert "status-atlas-s15" in resp.text
    assert "burn ratio" in resp.text.lower()


def test_team_page_unknown_404():
    assert client.get("/team/nope").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/web/test_pages.py -v`
Expected: FAIL (TemplateNotFound / 500) because the templates do not exist yet.

- [ ] **Step 3: Write `base.html`**

`sprintsight/web/templates/base.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Sprintsight{% endblock %}</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <header><a href="/" class="brand">Sprintsight</a> <span class="sub">watermelon detector</span></header>
  <main>{% block main %}{% endblock %}</main>
</body>
</html>
```

- [ ] **Step 4: Write `portfolio.html`**

`sprintsight/web/templates/portfolio.html`:

```html
{% extends "base.html" %}
{% block title %}Portfolio{% endblock %}
{% block main %}
<h1>Team portfolio</h1>
<p class="lede">Reported status versus what the data actually shows, as of Sprint 15.</p>
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

- [ ] **Step 5: Write `team.html`**

`sprintsight/web/templates/team.html`:

```html
{% extends "base.html" %}
{% block title %}{{ d.team }}{% endblock %}
{% block main %}
<p><a href="/">&larr; Back to portfolio</a></p>
<h1>
  {{ d.team }}
  {% if d.has_verdict and d.is_watermelon %}
    <span class="badge badge-watermelon">watermelon</span>
  {% endif %}
</h1>
<p class="headline">{{ d.headline }}</p>

{% if d.has_verdict %}
<p>
  Reported <span class="rag rag-{{ d.reported_status }}">{{ d.reported_status }}</span>,
  computed actual <span class="rag rag-{{ d.actual_status }}">{{ d.actual_status }}</span>.
</p>

<h2>Why</h2>
<p class="explanation">{{ d.explanation }}</p>

<h2>Signals</h2>
<ul class="signals">
  {% for s in d.signals %}<li>{{ s }}</li>{% endfor %}
</ul>

<h2>Evidence</h2>
<ul class="evidence">
  {% for e in d.evidence %}
    <li>
      <strong>{{ e.title }}</strong>
      <code>{{ e.artifact_id }}</code>
      {% if e.snippet %}<div class="snippet">{{ e.snippet }}</div>{% endif %}
    </li>
  {% endfor %}
</ul>
{% else %}
<p class="explanation">{{ d.explanation }}</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Fill in `app.css`**

Replace `sprintsight/web/static/app.css` with:

```css
:root { --green:#1a7f37; --amber:#bf8700; --red:#cf222e; --ink:#1c2024; --line:#e3e6ea; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; color: var(--ink);
  margin: 0; background: #fafbfc; }
header { padding: 14px 24px; border-bottom: 1px solid var(--line); background: #fff; }
.brand { font-weight: 700; text-decoration: none; color: var(--ink); }
.sub { color: #6b7280; }
main { max-width: 880px; margin: 0 auto; padding: 24px; }
h1 { font-size: 1.5rem; }
.lede, .headline { color: #4b5563; }
table.portfolio { width: 100%; border-collapse: collapse; background: #fff; }
table.portfolio th, table.portfolio td { text-align: left; padding: 10px 12px;
  border-bottom: 1px solid var(--line); }
tr.watermelon { background: #fff5f5; }
.rag { padding: 2px 8px; border-radius: 10px; font-size: .85rem; color: #fff; text-transform: capitalize; }
.rag-green { background: var(--green); } .rag-amber { background: var(--amber); }
.rag-red { background: var(--red); } .rag-unknown { background: #9aa1a9; }
.badge { padding: 2px 8px; border-radius: 6px; font-size: .8rem; }
.badge-watermelon { background: var(--red); color: #fff; }
.badge-ok { background: #eef2f5; color: #374151; }
.badge-muted { background: #f1f3f5; color: #6b7280; }
ul.signals li, ul.evidence li { margin: 6px 0; }
.snippet { color: #6b7280; font-size: .9rem; margin-top: 2px; }
code { background: #f1f3f5; padding: 1px 5px; border-radius: 4px; }
```

- [ ] **Step 7: Run the smoke tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/web/test_pages.py -v`
Expected: all PASS.

- [ ] **Step 8: Run the full suite + lint to confirm no regression**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check .`
Expected: all tests pass (prior 101 + the new web tests), ruff clean.

- [ ] **Step 9: Eyeball it locally (optional, manual)**

Start the server: `.venv/bin/uvicorn sprintsight.web.app:app --port 8000`
Open `http://localhost:8000/` and `http://localhost:8000/team/atlas`. Confirm Atlas is flagged and its drill-in shows signals + evidence. Stop with Ctrl-C.

- [ ] **Step 10: Commit**

```bash
git add sprintsight/web/templates sprintsight/web/static/app.css tests/web/test_pages.py
git commit -m "$(printf 'feat(stage6): server-rendered portfolio + watermelon drill-in pages [SS-6]\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: Wrap-up (HANDOVER + learning-queue flag)

**Files:**
- Modify: `HANDOVER.md` (Stage 6 first slice landed; how to run it)
- Modify: `HANDOVER.md` Learning queue (one flag line)

**Interfaces:**
- Consumes: nothing.
- Produces: updated state docs. No code.

- [ ] **Step 1: Update HANDOVER "Where we are"**

Add a Stage 6 section noting: first slice done on `stage6-watermelon-ui`; FastAPI app at `sprintsight/web/`; run with `.venv/bin/uvicorn sprintsight.web.app:app`; tests under `tests/web/` gate in CI via the `web` extra; offline, corpus-driven; auth/DB/LLM/polish still out of scope.

- [ ] **Step 2: Append one Learning queue flag line**

Append to the Learning queue section (flag only, do not teach):

```
- An "eval" for a UI tests the served data, not the pixels | Stage 6's gate asserts the FastAPI JSON/service output matches the watermelon ground truth (Atlas flagged, Echo insufficient), with light HTML smoke tests; the screen stays eval-first without screenshot testing | sprintsight/web/service.py + tests/web/ | flagged 2026-06-21
```

- [ ] **Step 3: Commit**

```bash
git add HANDOVER.md
git commit -m "$(printf 'docs(stage6): HANDOVER update + learning-queue flag for the watermelon UI [SS-6]\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Self-Review

**Spec coverage:**
- Portfolio view -> Task 3 (`portfolio()`) + Task 5 (`portfolio.html`). Covered.
- Drill-in with signals + evidence -> Task 2 (signals field) + Task 3 (`team_detail`) + Task 5 (`team.html`). Covered.
- Four routes (2 HTML, 2 JSON) -> Task 4 (JSON) + Task 5 (HTML). Covered.
- Reuse existing detector path -> Task 3 uses `graph_detector()`; only additive `Verdict.signals` change (Task 2). Covered.
- Eval-first, RED before code, offline, against Sprint-15 ground truth -> Tasks 2/3/4/5 each write failing tests first. Covered.
- Echo insufficient-evidence handling -> Task 3 (`_has_minimum`, `_insufficient_*`) + tests. Covered.
- Unknown team 404 -> Task 4 tests + `team_detail` returns None. Covered.
- `web` optional extra + CI install -> Task 1. Covered.
- Out of scope (auth/DB/LLM/polish/HTMX) -> not built; HTMX dropped (plain navigation), noted in plan intro and Task 5. Covered.

**Placeholder scan:** No TBD/TODO in code steps; every code step shows full content. The `app.css` placeholder in Task 4 is intentional (a real one-line file) and is replaced in Task 5 Step 6.

**Type consistency:** `TeamRow`, `TeamDetail`, `EvidenceItem` field names match between `service.py` (Task 3), the API `asdict()` serialization (Task 4), and the templates (Task 5: `row.is_watermelon`, `row.has_verdict`, `d.signals`, `d.evidence`, `e.title`, `e.artifact_id`, `e.snippet`). `Verdict.signals` defined in Task 2 is consumed in Task 3. `create_app()` defined in Task 4 is imported by tests in Tasks 4 and 5.
