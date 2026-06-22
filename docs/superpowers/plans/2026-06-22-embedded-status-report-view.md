# Embedded Status-Report View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the existing audience-tuned status-report writer on the team drill-in page, with a three-link audience switcher, served by the deterministic `compose` writer behind a seam.

**Architecture:** The web data layer (`service.py`) calls a module-level writer seam (default `compose`) with `{team, audience, artifacts}` and folds the resulting report into the `TeamDetail` view-model. The two team routes gain an optional `?audience=` query param. The drill-in template renders the report sections plus a cited Sources list and three audience links. HTML and JSON render from the same service output so they cannot drift.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, pytest, FastAPI `TestClient`. All offline (no Anthropic key, no DB).

## Global Constraints

- No new runtime dependencies. Use only what `.[dev,eval,web]` already provides.
- Web tests stay fully offline: the writer seam default is `compose`; the LLM writer is NOT activated in routes this slice.
- Tests run under `SPRINTSIGHT_ENV=dev` (set by `tests/web/conftest.py` chain / root conftest). Routes are login-gated; use the existing `client` fixture (logged in as ADMIN) for route tests.
- No JavaScript. Audience switching is plain links with a `?audience=` query param.
- Section keys stay snake_case (the machine contract); `heading_for(key)` is the ONLY place keys become human headings. Reuse it, do not duplicate heading logic.
- Default audience is `programme`. Valid audiences: `exec`, `programme`, `team`. Unknown value silently falls back to `programme` (no error page).
- No em dashes in any user-facing copy.

### Reference facts (verified against the real corpus, 2026-06-22)

- `compose({"team","audience","artifacts"})` returns a `Report` (`sprintsight/report/contract.py`):
  `sections: dict[str,str]`, `claims: list[Claim]` (each `Claim` has `text: str`, `citations: list[str]`), `insufficient_evidence: bool`.
- Atlas section keys per audience:
  - exec: `overall_rag`, `top_risks`, `ask`
  - programme: `overall_rag`, `risks`, `dependencies`, `milestones`
  - team: `sprint_metrics`, `ticket_progress`, `blockers`
- `heading_for` titles (from `sprintsight/report/render.py`): `overall_rag`→"Overall status", `top_risks`→"Top risks", `ask`→"Recommended next step", `risks`→"Risks", `dependencies`→"Dependencies", `milestones`→"Milestones", `sprint_metrics`→"Sprint metrics", `ticket_progress`→"Ticket progress", `blockers`→"Blockers".
- Atlas programme claims cite `status-atlas-s15` (the RAG claim) and `burndown-atlas-s15` (metric claims).
- Echo (`team_detail("echo")`) has no verdict → `compose` returns `insufficient_evidence=True`, empty sections.
- Note (not a bug): Atlas's report says "Overall status: green." while the detector flags Atlas as a watermelon (actual red). The report narrates the team's *reported* status; the watermelon verdict is the separate detector output. Both appearing on one page is the intended contrast.

---

## File Structure

- `sprintsight/web/service.py` (modify) — `ReportSection` dataclass; `DEFAULT_AUDIENCE`/`VALID_AUDIENCES`/`normalize_audience`; module-level `_writer` seam; new `TeamDetail` fields; report + sources derivation; `team_detail` gains `audience` arg; `_insufficient_detail` sets report-insufficient.
- `sprintsight/web/app.py` (modify) — `audience` query param on `GET /team/{id}` and `GET /api/team/{id}`.
- `sprintsight/web/templates/team.html` (modify) — audience switcher + Status report block + Sources.
- `sprintsight/web/static/app.css` (modify) — minimal styling for the switcher and report block.
- `tests/web/test_service.py` (modify) — service-level served-data tests.
- `tests/web/test_api.py` (modify) — JSON route audience tests.
- `tests/web/test_pages.py` (modify) — HTML smoke test.

---

## Task 1: Service layer — report on the TeamDetail view-model

**Files:**
- Modify: `sprintsight/web/service.py`
- Test: `tests/web/test_service.py`

**Interfaces:**
- Consumes: `compose` and `ReportWriter` from `sprintsight.report.writer`; `heading_for` from `sprintsight.report.render`; existing `artifacts_for`, `_SPRINTS`, `_evidence_item`, `EvidenceItem`, `TeamDetail`.
- Produces:
  - `ReportSection(heading: str, body: str)` frozen dataclass.
  - `DEFAULT_AUDIENCE = "programme"`, `VALID_AUDIENCES = ("exec", "programme", "team")`.
  - `normalize_audience(value: str) -> str`.
  - `TeamDetail` gains: `audience: str = DEFAULT_AUDIENCE`, `report_sections: list[ReportSection]`, `report_sources: list[EvidenceItem]`, `report_insufficient: bool = False`.
  - `team_detail(team_id: str, audience: str = DEFAULT_AUDIENCE) -> TeamDetail | None`.
  - Module-level `_writer: ReportWriter = compose`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_service.py`:

```python
from sprintsight.web import service


def test_team_detail_programme_report_sections_and_sources():
    d = service.team_detail("atlas", "programme")
    assert d is not None
    assert d.audience == "programme"
    assert d.report_insufficient is False
    headings = [s.heading for s in d.report_sections]
    assert "Overall status" in headings
    assert "Risks" in headings
    assert "Dependencies" in headings
    source_ids = {src.artifact_id for src in d.report_sources}
    assert "status-atlas-s15" in source_ids


def test_team_detail_exec_report_has_exec_sections_only():
    d = service.team_detail("atlas", "exec")
    headings = [s.heading for s in d.report_sections]
    assert "Top risks" in headings
    assert "Recommended next step" in headings
    assert "Sprint metrics" not in headings


def test_team_detail_team_audience_has_sprint_metrics():
    d = service.team_detail("atlas", "team")
    headings = [s.heading for s in d.report_sections]
    assert "Sprint metrics" in headings


def test_team_detail_unknown_audience_falls_back_to_programme():
    d = service.team_detail("atlas", "bogus")
    assert d.audience == "programme"


def test_team_detail_default_audience_is_programme():
    d = service.team_detail("atlas")
    assert d.audience == "programme"


def test_echo_report_is_insufficient():
    d = service.team_detail("echo")
    assert d is not None
    assert d.report_insufficient is True
    assert d.report_sections == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/pytest tests/web/test_service.py -k "report or audience or insufficient" -v`
Expected: FAIL (e.g. `TypeError: team_detail() takes 1 positional argument` or `AttributeError: 'TeamDetail' object has no attribute 'report_sections'`).

- [ ] **Step 3: Add imports and module constants**

In `sprintsight/web/service.py`, add to the imports near the existing ones:

```python
from sprintsight.report.render import heading_for
from sprintsight.report.writer import ReportWriter, compose
```

Below the `_detector = graph_detector()` line, add:

```python
DEFAULT_AUDIENCE = "programme"
VALID_AUDIENCES = ("exec", "programme", "team")

_writer: ReportWriter = compose  # seam; LLM writer can be injected here later


def normalize_audience(value: str) -> str:
    """Coerce any audience value to a valid one; unknown falls back to the default."""
    return value if value in VALID_AUDIENCES else DEFAULT_AUDIENCE
```

- [ ] **Step 4: Add the `ReportSection` dataclass and new `TeamDetail` fields**

Add a new frozen dataclass next to `EvidenceItem`:

```python
@dataclass(frozen=True)
class ReportSection:
    heading: str
    body: str
```

Extend the `TeamDetail` dataclass with these fields (after the existing `evidence` field):

```python
    audience: str = DEFAULT_AUDIENCE
    report_sections: list[ReportSection] = field(default_factory=list)
    report_sources: list[EvidenceItem] = field(default_factory=list)
    report_insufficient: bool = False
```

- [ ] **Step 5: Add the report-building helpers**

Add these helpers (near `_evidence_item`):

```python
def _report_sources(report, arts: dict[str, Artifact]) -> list[EvidenceItem]:
    """Unique cited artifacts behind the report's claims, in first-cited order."""
    seen: list[str] = []
    out: list[EvidenceItem] = []
    for claim in report.claims:
        for cid in claim.citations:
            if cid not in seen:
                seen.append(cid)
                out.append(_evidence_item(cid, arts))
    return out


def _report_for(
    team: str, audience: str, arts: dict[str, Artifact]
) -> tuple[list[ReportSection], list[EvidenceItem], bool]:
    """Run the writer seam and shape its report for display."""
    report = _writer({"team": team, "audience": audience, "artifacts": arts})
    if report.insufficient_evidence:
        return [], [], True
    sections = [ReportSection(heading_for(k), v) for k, v in report.sections.items()]
    return sections, _report_sources(report, arts), False
```

- [ ] **Step 6: Wire `team_detail` and `_insufficient_detail`**

Replace `team_detail` with:

```python
def team_detail(team_id: str, audience: str = DEFAULT_AUDIENCE) -> TeamDetail | None:
    team = _resolve_team(team_id)
    if team is None:
        return None
    audience = normalize_audience(audience)
    verdict = _verdict_or_none(team)
    if verdict is None:
        return _insufficient_detail(team, audience)
    arts = artifacts_for(team, _SPRINTS)
    sections, sources, insufficient = _report_for(team, audience, arts)
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
        audience=audience,
        report_sections=sections,
        report_sources=sources,
        report_insufficient=insufficient,
    )
```

Update `_insufficient_detail` to take the audience and mark the report insufficient:

```python
def _insufficient_detail(team: str, audience: str = DEFAULT_AUDIENCE) -> TeamDetail:
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
        audience=normalize_audience(audience),
        report_sections=[],
        report_sources=[],
        report_insufficient=True,
    )
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/pytest tests/web/test_service.py -v`
Expected: PASS (all existing + new).

- [ ] **Step 8: Lint**

Run: `.venv/bin/ruff check sprintsight/web/service.py tests/web/test_service.py`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add sprintsight/web/service.py tests/web/test_service.py
git commit -m "feat(stage6): report on TeamDetail behind a writer seam [SS-6]"
```

---

## Task 2: Routes — `?audience=` on the two team routes

**Files:**
- Modify: `sprintsight/web/app.py`
- Test: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `service.team_detail(team_id, audience)`, `service.DEFAULT_AUDIENCE`.
- Produces: `GET /team/{id}?audience=` (HTML) and `GET /api/team/{id}?audience=` (JSON), both passing the param through. `asdict(detail)` now includes `audience`, `report_sections`, `report_sources`, `report_insufficient`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_api.py`:

```python
def test_api_team_audience_param_selects_exec(client):
    body = client.get("/api/team/atlas?audience=exec").json()
    assert body["audience"] == "exec"
    headings = {s["heading"] for s in body["report_sections"]}
    assert "Recommended next step" in headings
    assert "Sprint metrics" not in headings


def test_api_team_default_audience_is_programme(client):
    body = client.get("/api/team/atlas").json()
    assert body["audience"] == "programme"
    headings = {s["heading"] for s in body["report_sections"]}
    assert "Risks" in headings
    assert {src["artifact_id"] for src in body["report_sources"]}


def test_api_team_unknown_audience_falls_back(client):
    body = client.get("/api/team/atlas?audience=bogus").json()
    assert body["audience"] == "programme"


def test_api_echo_report_insufficient(client):
    body = client.get("/api/team/echo").json()
    assert body["report_insufficient"] is True
    assert body["report_sections"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/pytest tests/web/test_api.py -k audience -v`
Expected: FAIL with `KeyError: 'audience'` (the field is not serialized yet).

- [ ] **Step 3: Add the query param to both team routes**

In `sprintsight/web/app.py`, change `api_team` to accept the param:

```python
    @app.get("/api/team/{team_id}")
    def api_team(  # noqa: B008
        team_id: str,
        audience: str = service.DEFAULT_AUDIENCE,
        user: User = Depends(require_api_user),
    ) -> dict:
        detail = service.team_detail(team_id, audience)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return asdict(detail)
```

And change `page_team`:

```python
    @app.get("/team/{team_id}", response_class=HTMLResponse)
    def page_team(
        request: Request, team_id: str, audience: str = service.DEFAULT_AUDIENCE
    ) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        detail = service.team_detail(team_id, audience)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return _TEMPLATES.TemplateResponse(request, "team.html", {"d": detail, "user": user})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/pytest tests/web/test_api.py -v`
Expected: PASS (existing + new). The `test_api_team_unknown_404` test still passes (unknown team → 404 before audience matters).

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check sprintsight/web/app.py tests/web/test_api.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/web/app.py tests/web/test_api.py
git commit -m "feat(stage6): audience query param on team routes [SS-6]"
```

---

## Task 3: Template + CSS — switcher and report block

**Files:**
- Modify: `sprintsight/web/templates/team.html`
- Modify: `sprintsight/web/static/app.css`
- Test: `tests/web/test_pages.py`

**Interfaces:**
- Consumes: `d.team`, `d.has_verdict`, `d.audience`, `d.report_insufficient`, `d.report_sections` (each `.heading`, `.body`), `d.report_sources` (each `.title`, `.artifact_id`).
- Produces: rendered HTML containing "Status report", three `?audience=` links, the section headings, and a Sources list.

- [ ] **Step 1: Write the failing smoke test**

Add to `tests/web/test_pages.py`:

```python
def test_team_page_shows_report_and_audience_switch(client):
    html = client.get("/team/atlas").text
    assert "Status report" in html
    assert "?audience=exec" in html
    assert "?audience=programme" in html
    assert "?audience=team" in html
    assert "Risks" in html  # programme default section heading


def test_team_page_exec_audience_renders_exec_section(client):
    html = client.get("/team/atlas?audience=exec").text
    assert "Recommended next step" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/pytest tests/web/test_pages.py -k "report or audience" -v`
Expected: FAIL ("Status report" not found in HTML).

- [ ] **Step 3: Add the report block to the template**

In `sprintsight/web/templates/team.html`, inside the `{% if d.has_verdict %}` branch, after the Evidence `</ul>`, add:

```html
<h2>Status report</h2>
<p class="audience-switch">
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
  <h3>Sources</h3>
  <ul class="sources">
    {% for src in d.report_sources %}
      <li><strong>{{ src.title }}</strong> <code>{{ src.artifact_id }}</code></li>
    {% endfor %}
  </ul>
{% endif %}
```

- [ ] **Step 4: Add minimal CSS**

Append to `sprintsight/web/static/app.css`:

```css
.audience-switch { margin: 0.5rem 0 1rem; }
.audience-switch .aud {
  display: inline-block;
  margin-right: 0.5rem;
  padding: 0.15rem 0.6rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  text-decoration: none;
  color: #333;
}
.audience-switch .aud-active {
  background: #1f6feb;
  border-color: #1f6feb;
  color: #fff;
}
.report-body { white-space: pre-wrap; margin: 0 0 1rem; }
.sources { color: #555; font-size: 0.9rem; }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/pytest tests/web/test_pages.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full web suite + lint**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/pytest tests/web -v`
Expected: all PASS.

Run: `.venv/bin/ruff check sprintsight tests`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add sprintsight/web/templates/team.html sprintsight/web/static/app.css tests/web/test_pages.py
git commit -m "feat(stage6): drill-in report block + audience switcher [SS-6]"
```

---

## Task 4: Full-suite verification + manual smoke

**Files:** none (verification only).

- [ ] **Step 1: Run the entire test suite**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/pytest -q`
Expected: all pass (prior 152 + the new tests), 3 skipped as before.

- [ ] **Step 2: Run the deterministic eval gates (must stay green)**

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: report eval 4/4 PASS.

Run: `.venv/bin/python scripts/run_watermelon_eval.py`
Expected: watermelon eval green (4/4 + 4/4). (If the script name differs, use the one wired into CI `lint-and-test`.)

- [ ] **Step 3: Manual smoke (optional but recommended)**

Run: `SPRINTSIGHT_ENV=dev .venv/bin/uvicorn sprintsight.web.app:app --port 8000`
Then log in and visit `/team/atlas`, click Exec / Programme / Team, confirm the report and Sources change and the active link is highlighted. Visit `/team/echo` and confirm the insufficient-evidence message. Stop the server.

- [ ] **Step 4: Update HANDOVER + learning-queue flag**

Add a Stage 6 entry noting the embedded report view, and append one line to the HANDOVER `Learning queue`:
`audience-tuned reporting | same data, three audience-shaped reports, now switchable in the web UI | sprintsight/web/service.py + templates/team.html | 2026-06-22`

```bash
git add HANDOVER.md
git commit -m "docs(stage6): HANDOVER + learning-queue flag for embedded report view [SS-6]"
```

---

## Self-review notes

- **Spec coverage:** placement (Task 3), writer seam default compose (Task 1 `_writer`), audience switcher via `?audience=` (Tasks 2+3), default programme (Task 1), sources/citations (Task 1 `_report_sources` + Task 3 list), insufficient-evidence Echo (Task 1 `_insufficient_detail` + Task 3 message), HTML/JSON from one service output (Tasks 1-2), login gate unchanged (Task 2 keeps `session_user`/`require_api_user`), served-data eval not pixels (Tasks 1-3 tests). All covered.
- **LLM writer not switched on:** `_writer = compose` only; no key path in routes. Matches spec out-of-scope.
- **Type consistency:** `team_detail(team_id, audience)`, `ReportSection(heading, body)`, `report_sections`/`report_sources`/`report_insufficient`/`audience` used identically across service, routes (via `asdict`), template, and tests.
