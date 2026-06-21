# Stage 6 first slice: the Watermelon screen

Date: 2026-06-21
Stage: 6 (Portfolio + Watermelon UI, Epic SS-6)
Status: design — awaiting review

## Plain-English summary (read this first)

The watermelon detector (a team reported **green** but is actually **red**) already works,
but only inside the test harness. Nobody has ever *seen* it. This is the first time it
becomes a screen you can point at.

We are building a small web app with two views:

1. **Portfolio** — every team in one grid: its reported status, its computed actual status,
   and a watermelon badge when the two disagree (looks healthier than it is).
2. **Drill-in** — click a team to see *why*: the plain-English explanation, the signals
   (burn ratio, velocity decline, hidden dependency), and the evidence (the exact artifacts
   that prove it). The drill-in is what makes the flag credible instead of a guess.

Three deliberate choices, decided in brainstorming:

- **First brick of the real product, not a throwaway demo.** So we build a real serving
  layer (a FastAPI web app) that Stage 5 login and real data can attach to later, not a
  pile of static HTML files.
- **Server-rendered, one language.** The app is Python end to end (FastAPI + Jinja2 HTML
  templates + a little HTMX for the drill-in). No separate JavaScript app, no build
  toolchain. Leanest thing that is still a real server.
- **Eval-first still holds.** We test the *data* the screen serves, not the pixels, and we
  write those tests RED before any app code, the same red-to-green rule as every prior
  stage.

Out of scope on purpose: login, a persistent database, the LLM status report, any write or
RAID action, and visual polish (that is Stage 7). This slice is corpus-driven and runs fully
offline (no API key, no database).

## Decision

Add a new `sprintsight/web/` package: a FastAPI app that reads the synthetic team corpus
through the **existing detector path** and renders a portfolio grid plus a per-team drill-in.
The detector is reused as-is, never re-implemented. Web tools ship as a new optional `web`
dependency extra; CI installs `.[dev,web]` so the new tests gate.

This is "Option A: FastAPI server-rendered" from brainstorming. "Option B" (React single-page
app on a JSON API) and "Option C" (static pre-rendered HTML, no server) are explicitly out of
scope.

## Design

### Components (new package `sprintsight/web/`)

- **`service.py`** — the data layer, the unit we test hardest. Pure Python, no HTTP, no LLM,
  no database. Two functions:
  - `portfolio() -> list[TeamRow]` — a view-model row per team.
  - `team_detail(team_id: str) -> TeamDetail` — one team's verdict with its evidence resolved
    to readable labels.
  Both read the corpus via the existing fixtures loader and call the existing detector path
  (the same entry the watermelon eval gates). The detector sits **behind this seam** so a
  future DB-backed detector can replace it without touching the pages.
- **`app.py`** — `create_app() -> FastAPI` builds the app and wires routes. No module-level
  app side effects beyond the factory.
- **`templates/`** — Jinja2: `portfolio.html`, `team.html`. A small HTMX swap drives the
  drill-in.
- **`static/`** — minimal CSS plus a **vendored** HTMX file (committed to the repo, not a
  CDN link) so the app and CI stay fully offline.

### View models (the contract the templates and JSON share)

- `TeamRow`: `team`, `reported_status`, `actual_status`, `is_watermelon`, `headline`
  (the one-line explanation), `has_verdict` (false for thin-data teams).
- `TeamDetail`: everything in `TeamRow` plus `signals: list[str]`, `explanation: str`, and
  `evidence: list[EvidenceItem]`.
- `EvidenceItem`: `artifact_id`, `source_type`, `sprint`, `title` (readable label), `snippet`
  (a short excerpt of the artifact body).

Statuses are the existing `green`/`amber`/`red` strings. No new vocabulary.

### Routes

| Method + path          | Returns            | Notes                                            |
|------------------------|--------------------|--------------------------------------------------|
| `GET /`                | HTML portfolio     | renders `portfolio()`                            |
| `GET /team/{team_id}`  | HTML drill-in      | renders `team_detail()`; 404 on unknown team     |
| `GET /api/portfolio`   | JSON list[TeamRow] | the same data as `/`, machine-readable           |
| `GET /api/team/{id}`   | JSON TeamDetail    | the API seam for later auth / richer frontend    |

The HTML routes and the JSON routes render from the **same** `service.py` output, so they can
never drift.

### Data flow

corpus files -> fixtures loader -> per-team artifacts -> existing detector path -> `Verdict`
-> `service.py` shapes the view-model -> JSON response **or** Jinja template -> browser.

### Error handling

- **Unknown team** -> HTTP 404.
- **Thin-data team (Echo)** -> required artifacts (status / burndown / RAID) may be missing.
  `service.py` catches the lookup and returns a row with `has_verdict = false` and an
  "insufficient evidence" headline. It is rendered as a neutral row. **Never a crash, never a
  false flag.** This is asserted by a test.
- **Per-team isolation** -> a failure computing one team must not break the portfolio; the
  affected team degrades to the "insufficient evidence" state and the others render normally.

### Eval-first: the Stage 6 gate

We honour "no feature code before its eval exists" by testing the served data against the
ground truth that already exists (`data/ground-truth/labels.yaml`). Tests are written RED
first, then made GREEN by the implementation. All run **offline** in CI (no key, no DB) and
join the existing `lint-and-test` job.

The portfolio judges **as-of Sprint 15** (the detector's existing judging point: Sprint 15
with Sprint 14 as context), so the expected values are the **Sprint-15** verdict blocks in
`labels.yaml`. The ground truth carries a Sprint-14 block per team as well; we do not assert
against it in this slice. Echo has **no** watermelon verdict in the ground truth (it is the
thin-data report case: a one-line status, no metrics or RAID), which is exactly why its
expected state is "insufficient evidence".

1. `tests/web/test_service.py`
   - `portfolio()` returns every team with the correct Sprint-15 verdict vs ground truth:
     Atlas `is_watermelon = true` / actual `red`; Boreas `false` / `green`; Cygnus `false` /
     `amber`; Draco `false` / `amber`.
   - Echo returns `has_verdict = false` (insufficient evidence), not a crash and not a flag.
   - `team_detail("atlas")` includes the required evidence artifact ids and the signals.
2. `tests/web/test_api.py` (FastAPI `TestClient`)
   - `GET /api/portfolio` returns 200 and the correct verdict per team.
   - `GET /api/team/atlas` returns 200 with the watermelon verdict, signals, and evidence.
   - `GET /api/team/unknown` returns 404.
3. `tests/web/test_pages.py` (smoke)
   - `GET /` returns 200 and contains each team name and its RAG.
   - `GET /team/atlas` returns 200 and contains the explanation and the evidence labels.

The deterministic watermelon and report evals remain the existing CI gate, unchanged.

### Dependencies

New optional extra in `pyproject.toml`:

```
[project.optional-dependencies]
web = ["fastapi>=0.110", "jinja2>=3", "httpx>=0.27", "uvicorn>=0.30"]
```

- `httpx` is the FastAPI test client used by the eval tests.
- `uvicorn` runs the server locally; not needed for the tests.
- The core library still imports with no web deps. CI's `lint-and-test` job installs
  `.[dev,web]` so the Stage 6 tests run and gate.
- Local install (`pip install -e .[dev,web]`) is the first implementation step, run only when
  the user is asked, never before.

## Out of scope (YAGNI)

- Login / auth / sessions — Stage 5 (SS-8). The JSON API seam is where it attaches later.
- Persistent database — still corpus-driven; the real-wiring items stay deferred.
- The embedded audience-tuned LLM status report — keeps the LLM out of this slice.
- Any write, RAID action, filtering, sorting, or real-time refresh.
- Visual polish and theming — Stage 7 (SS-5). The watermelon badge is a simple
  green-outside / red-inside motif and nothing more.

## Risks and mitigations

- **Detector contract assumes full artifacts.** `detect()` indexes required artifacts
  directly, so a thin team would raise. Mitigation: the service guards required-artifact
  lookups and degrades to "insufficient evidence" (tested on Echo).
- **CI must stay offline.** Mitigation: HTMX is vendored, no CDN; no API key or DB touched;
  the web tests are corpus-only and deterministic.
- **Scope creep toward a full app.** Mitigation: the out-of-scope list above is part of the
  spec; anything on it needs its own story.

## Learning queue flag (candidate)

This slice introduces the project's first HTTP serving layer and the idea of an "eval" for a
UI being a test of the served data, not the pixels. If that reads as a genuinely new concept
for a non-engineer, add one line to the HANDOVER Learning queue when the work lands.
