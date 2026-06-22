# Embedded status-report view (Stage 6 slice) — design

Date: 2026-06-22
Stage: 6 (Web app, Epic SS-6)
Status: approved (brainstorm), spec under review

## Plain-English summary (read this first)

We already have two things that have never met:

1. A **drill-in page** in the web app (`/team/atlas`) that shows the watermelon verdict,
   the signals, and the evidence list for one team.
2. A **status-report writer** that turns a team's data into an audience-tuned narrative
   (exec, programme, or team). Today it only runs from a script, never in the browser.

This slice connects them: the drill-in page gains a **Status report** block that shows the
writer's output, with three links to switch audience. The plumbing exists on both ends; we
are wiring them together. No new AI capability, no database, no writes.

## Decisions (settled in brainstorm)

- **Placement:** embed the report on the existing drill-in page, below the verdict and
  evidence. One page holds everything about a team.
- **Writer:** the deterministic `compose` writer is the default (offline, testable, the
  current CI gate). The LLM writer stays injectable behind the existing writer seam but is
  NOT switched on in the routes this slice, so web tests stay fully offline.
- **Audience:** a three-link switcher (Exec / Programme / Team) driven by a `?audience=`
  query parameter. No JavaScript, plain page navigation. Default audience: `programme`.

## What the user sees

On `/team/{id}`, below the existing verdict / signals / evidence:

- Three links near the top of the new block: **Exec | Programme | Team**. Each is a plain
  link to the same page with `?audience=exec` (etc.). The active one is marked.
- A **Status report** block rendering the report's sections (heading + prose) for the
  selected audience.
- Underneath, a short **Sources** list: the citations the writer attached to its claims,
  shown with the same artifact-to-label mapping the evidence list already uses. This makes
  the "fully-cited" promise visible.

When no `audience` param is present, the page renders the `programme` report.

## How it is wired (data flow)

The web data layer (`sprintsight/web/service.py`) changes as follows:

- `team_detail(team_id, audience="programme")` gains the `audience` argument. It already
  gathers the team's artifacts (`artifacts_for(team, _SPRINTS)`); it now also calls the
  **writer seam** with `{"team": team, "audience": audience, "artifacts": arts}` and folds
  the resulting report into the returned `TeamDetail` view-model.
- New view-model fields on `TeamDetail` (frozen dataclass, same style as today):
  - `audience: str` — the audience actually rendered.
  - `report_sections: list[ReportSection]` — `(heading, body)` pairs for display, ordered by
    the audience profile's section order (`AudienceProfile.sections`), not dict insertion,
    with `heading_for(key)` supplying each heading.
  - `report_sources: list[EvidenceItem]` — the cited artifacts behind the report's claims,
    deduplicated, reusing the existing `EvidenceItem` shape and source labels.
  - `report_insufficient: bool` — true when the writer abstains (thin data).
- A new small frozen `ReportSection` dataclass (`heading: str`, `body: str`).
- The **writer seam** is a module-level default the app can override, mirroring how
  `_detector = graph_detector()` already works: `_writer = compose`. `team_detail` calls
  `_writer(inputs)`. This is the seam behind which the LLM writer can later be injected; we
  do not inject it this slice.

HTML and JSON both render from this one service output, so they cannot drift (the existing
rule for this app).

## Routes (`sprintsight/web/app.py`)

- `GET /team/{id}?audience=` (HTML) — reads the optional `audience` query param, validates
  it against `{exec, programme, team}`, falls back to `programme` on any unknown value (no
  error page), passes it to `team_detail`, renders the template.
- `GET /api/team/{id}?audience=` (JSON) — same param handling; serializes the report fields
  alongside the existing detail fields.
- Both routes stay login-gated by the Stage 5 auth dependency, unchanged.
- Unknown team still returns 404, unchanged.

## Templates

- `templates/team.html` gains the audience switcher (three links) and the report block
  (sections + sources). Plain server-rendered HTML, no JavaScript. The switcher marks the
  active audience. `static/app.css` gains minimal styling for the block and active link.

## Edge cases

- **Insufficient evidence (Echo):** the writer already returns a `Report` with
  `insufficient_evidence=True`. The service sets `report_insufficient=True` and the template
  shows a plain "Not enough evidence to write a report" message instead of empty sections.
  No crash, no fabricated content.
- **Unknown audience value:** silently falls back to `programme`.
- **Unknown team:** 404 as today.

## Eval-first (the gate for this slice)

Consistent with the watermelon UI slice, the eval is **served-data tests, not pixels**. The
report's own correctness is already covered by the existing report-quality eval
(`scripts/run_report_eval.py`, 4/4); these tests only prove the web layer serves it
faithfully and selects the right audience.

New / extended tests under `tests/web/`:

- For **Atlas**, for each of the three audiences, assert the served `TeamDetail` carries the
  expected grounded facts for that audience: the RAG line is present, a known risk line
  appears, and the section set matches the audience profile (e.g. exec has no sprint-metrics
  section; team does).
- Assert **Echo**'s drill-in serves `report_insufficient=True` and no fabricated sections.
- Assert the `audience` query param selects the audience, and an unknown value falls back to
  `programme`.
- Light HTML smoke test: the three audience links and the report block render on the page;
  the JSON route exposes the report fields.

All offline, corpus-driven, no key, no DB. CI `lint-and-test` continues to install
`.[dev,eval,web]` and run ruff + pytest + the report eval gate.

## Out of scope (deferred, on purpose)

- Live LLM-authored prose in the browser (seam present, not switched on this slice).
- Rich markdown-to-HTML rendering beyond plain sections.
- Persistent DB, writes/RAID actions, signup/account flows.
- Remembering the chosen audience across pages or per user.

## Files touched (anticipated)

- `sprintsight/web/service.py` — `audience` arg, writer seam, new view-model fields,
  `ReportSection` dataclass, sources derivation.
- `sprintsight/web/app.py` — `audience` query param on the two team routes.
- `sprintsight/web/templates/team.html` — switcher + report block.
- `sprintsight/web/static/app.css` — minimal styling.
- `tests/web/` — new served-data + smoke tests.

## Learning queue flag

This slice surfaces the audience-tuned report (a core differentiator) in the UI for the
first time. Candidate one-line flag for the HANDOVER learning queue:
"audience-tuned reporting | same data, three audience-shaped reports, now switchable in the
web UI | sprintsight/web/service.py + templates/team.html | 2026-06-22".
