# Stage 7 first slice — UX Polish (demo-ready visual identity)

Date: 2026-06-22
Epic: SS-5 (UX Polish + Connectors, stage-7)
Status: design approved, ready for implementation plan

## Plain-English summary (read this first)

The web app works but looks generic. This slice gives it a real, distinctive look so it
demos like a finished product. We picked one visual direction ("Calm SaaS": clean, airy,
modern, like Linear or Notion) and we restyle the screens we already have. We add no new
pages and no new technology. The one piece of genuinely new *behaviour* is a small summary
band on the portfolio page that shows headline numbers (how many watermelons, how many
teams). Because that is new served data, that is the part we test first.

This is the **first** of two Stage 7 slices. The second slice (real MCP connectors) is a
separate spec, separate plan, later.

## Goal

A demo-ready visual identity across the existing five screens, in the approved
"Direction A — Calm SaaS" style, without changing any report logic, watermelon logic, or
auth logic.

## What the user approved (visual decisions, locked)

1. **Direction A — Calm SaaS.** Clean and airy, generous whitespace, muted slate/ink text,
   an emerald-green accent (ties to the green/red RAG story), rounded cards, system-ui type.
2. **Portfolio shell = top bar + summary band.** A top header (logo mark + brand + session)
   and a row of headline KPI cards above the team table.
3. **Team drill-in treatment:** a watermelon **verdict banner** at the top (red-tinted card,
   the 🍉 emoji, "reported green but actually red"), the audience switcher rendered as
   **tabs**, and evidence/sources as cited **cards** rather than bare bullets.
4. **Keep the 🍉 emoji** on the verdict banner (only there).
5. **Login + admin: light consistency pass** — adopt the shell, tokens, and fonts; no
   bespoke redesign.

Approved mockups are preserved under `.superpowers/brainstorm/` (gitignored):
`visual-direction.html`, `shell-layout.html`, `team-page.html`.

## Scope

### In scope
- **`sprintsight/web/static/app.css`** — rebuilt as a small design system: CSS custom-property
  tokens (color, spacing scale, radius, type scale) plus component styles for the shell, KPI
  cards, RAG chips, flag badges, verdict banner, audience tabs, and evidence/source cards.
  No CSS framework, no build step — hand-written CSS served as a static file (as today).
- **`sprintsight/web/templates/base.html`** — top-bar shell: logo mark, brand, session block.
- **`sprintsight/web/templates/portfolio.html`** — add the summary band above the table; restyle
  the table to the new tokens.
- **`sprintsight/web/templates/team.html`** — verdict banner, audience tabs, cited evidence/source
  cards. Report prose, headings, and the section loop are unchanged in meaning.
- **`sprintsight/web/templates/login.html`** and **`admin_accounts.html`** — light pass to inherit
  the shell and tokens.
- **`sprintsight/web/service.py`** — compute and expose the **portfolio summary counts** (the only
  new served data; see Data below).
- **Tests** under `tests/web/` — summary-count contract test (written first) + light HTML smoke
  tests for the new template structures.

### Out of scope (YAGNI / deferred)
- MCP connectors and any real-data ingestion (the *other* Stage 7 slice, separate spec).
- Mobile/responsive deep work beyond what fluid tokens naturally give. Target is desktop demo.
- Any JavaScript framework, client-side state, or a front-end build step. Stays server-rendered
  Jinja + plain CSS. The audience tabs remain plain links (no JS), styled as tabs.
- Charts, graphs, dark mode, theming switches.
- New pages or new routes. URLs and the page set are unchanged.
- Any change to report-writer logic, watermelon evaluation, auth, the LLM gate, or the cache.

## Architecture / where the change lives

Server-rendered FastAPI + Jinja2, exactly as today. The slice is overwhelmingly
**presentation** (one CSS file + four templates). The single non-presentation change is a
small, pure, read-only addition in `service.py` that derives summary counts from data the
portfolio already loads.

### Components and boundaries
- **`app.css` (design system):** owns all look-and-feel. Templates reference semantic classes;
  they carry no inline styling decisions. Changing a token must not require template edits.
- **Templates (structure):** own page structure and which data binds where. They consume the
  same view-model fields as today, plus the new `summary` object on the portfolio.
- **`service.py` (data):** owns what is served. New: a `PortfolioSummary` derived from the
  existing portfolio rows. Pure function of data already in hand — no new I/O, no new query,
  no LLM call.

## Data flow (the one new contract)

The portfolio page already builds a list of team rows, each with `is_watermelon` and a
verdict/`has_verdict` flag. This slice adds a derived summary computed from those same rows:

- `watermelons` — count of rows where `is_watermelon` is true.
- `teams_tracked` — total team rows.
- `insufficient` — count of rows with no verdict (insufficient evidence).
- `sprint` — the current sprint label already present in the portfolio context.

`service.py` computes this once from the rows it already has and passes it to the template as
`summary`. No new data source; it is a fold over existing data, so it cannot disagree with the
table beneath it.

For the seed corpus the verified expected values are: **teams_tracked = 5 (Atlas, Boreas,
Cygnus, Draco, Echo), watermelons = 1 (Atlas: reported green, actual red), insufficient = 1
(Echo: no verdict).** The test pins these to the ground-truth fixtures rather than to literals
duplicated in `service.py`. (Note: the brainstorm mockups showed four illustrative teams with
placeholder names; the real corpus is these five.)

## Error handling / edge cases
- **Empty portfolio:** summary shows zeros; band still renders (no divide-by-anything, counts only).
- **All-consistent portfolio:** `watermelons = 0`; the alert KPI styles to a neutral (not red) state.
- **Missing/unknown statuses:** RAG chip falls back to the existing `unknown` styling; no crash.
- **No regression risk to logic:** verdicts, report contract, and auth are untouched, so their
  existing tests continue to gate them.

## Testing (eval-first; tests written before implementation)

Consistent with the Stage 6 precedent "an eval for a UI tests the served data, not the pixels":

1. **Summary-count contract test (write first, must fail first):** assert `service.py` returns a
   `summary` whose counts match the watermelon ground truth for the seed corpus (1 watermelon,
   1 insufficient, N teams). This is the new behaviour and its red→green gate.
2. **Per-shape isolation:** a synthetic all-consistent input yields `watermelons = 0`; an
   all-insufficient input yields `insufficient = N`. Guards the fold's correctness independent of
   the seed fixture.
3. **Light HTML smoke tests:** the rendered portfolio contains the summary band markup; the
   rendered team page contains the verdict banner (when watermelon) and exactly three audience
   tabs with the active one marked. Structure-level assertions only, not pixel/style.
4. **Unchanged gates stay green:** full suite (currently 174 passed + 3 skipped), ruff clean, and
   the deterministic watermelon (4/4) + report (4/4) eval gates remain the CI gate, unaffected.

## Security / data residency
No new external calls, no new persisted data, no auth change. The summary is derived in-process
from data already loaded. ZDR posture and the offline-by-default stance are unchanged. Nothing
in this slice touches the live-LLM gate or the session cookie.

## Learning-queue flag (for HANDOVER, training thread consumes)
A genuinely new concept for a non-engineer: **a design system / design tokens** — why the look
lives in named CSS variables (one place to change a color) rather than being sprinkled across
templates. Flag one line in HANDOVER's Learning queue at implementation time.

## Definition of done
- Tests above written first, then green; full suite + ruff clean; deterministic eval gates
  unchanged and green.
- All five screens render in Direction A with no visual inconsistency between them.
- HANDOVER.md updated; Learning-queue line added; Jira SS-5 slice Story walked
  Backlog → To Do → In Progress → In Review → Done with a completion comment.
- No change to report logic, watermelon logic, auth, the LLM gate, or the cache.
