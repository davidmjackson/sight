# Spec: Align Sprintsight with the suite (Instrument) design system

Date: 2026-06-30
Status: Approved (design), ready for implementation plan
Topic: web UI restyle to the shared Sprint Suite design language

## Plain-English summary (read this first)

The Sprint Suite (Signal, Plan, Retrospective, RAID, Poker, Hub) shares one named design
system called **Instrument**: a single core stylesheet plus self-hosted fonts, an icon
sprite, and a signature animated "scope trace" header. Sprintsight today has its own
standalone styling (the Stage 7 design tokens in `static/app.css`). This slice reskins all
five Sprintsight web pages to Instrument so the app visibly belongs to the suite.

Approach (decided with David): a **faithful local copy plus a drift guard**, not full
registration into the suite's Node build tooling. Sprintsight gets an **indigo accent**
(its identity in the suite) and a **reticle glyph** (circle + crosshair + centre dot).
No detector, report, or eval logic changes; only markup, classes, and static assets.

## Decisions locked in brainstorming

1. **Consumption model:** faithful copy of the Instrument assets into Sprintsight + a test
   that flags drift from the suite source. NOT full registration into the suite's Node
   sync/drift tooling (deferred "full member" path; Sprintsight is Python, the tooling is
   Node).
2. **Scope:** all five pages (login, portfolio, team drill-in, cross-tool, admin accounts).
3. **Accent identity:** indigo/blue, the unused hue between Retro's teal and Plan's violet,
   chosen so it does NOT collide with the red/amber/green watermelon verdict colours.
4. **Glyph:** a reticle (circle + crosshair + centre dot), abstract and on-theme with the
   suite's geometric glyphs and the Instrument oscilloscope motif.

## Context (verified)

- Sprintsight web is FastAPI + Jinja2. One shell `sprintsight/web/templates/base.html`;
  five content templates (`login.html`, `portfolio.html`, `team.html`, `crosstool.html`,
  `admin_accounts.html`); one stylesheet `sprintsight/web/static/app.css` (169 lines);
  static mounted at `/static`. Templates have ZERO inline `style=` and ZERO inline
  `<script>` (so the suite's strict no-inline approach is already satisfied).
- Instrument source: `/var/www/suite/shared/theme/` = `instrument-core.css`,
  `oscilloscope.js`, `glyphs.svg`, `fonts/` (8 `.woff2`), plus Node tooling we do NOT copy
  (`sync-theme.mjs`, `check-theme-drift.mjs`, `manifest.mjs`, `tests/`).
- Asset paths are ABSOLUTE web-root in Instrument: `instrument-core.css` `@font-face`
  references `url("/fonts/...woff2")`; suite pages link `/css/instrument-core.css`,
  `/css/<app>.css`, `/js/oscilloscope.js` (type=module), and the brand mark uses
  `<use href="/illos/glyphs.svg#glyph-<app>"/>`. So the assets MUST be served at web-root
  `/css`, `/js`, `/illos`, `/fonts` for the copied files to work unchanged.
- Instrument tokens are `oklch()`; per-app accents: Signal green (162), Retro teal (206),
  RAID amber (72), Plan violet/plum (290), Poker/Hub green. Spacing/radius/shadow tokens
  are defined per-app (not in the foundation) with identical values across apps.

## Goal and success criteria

Goal: all five Sprintsight pages render in the Instrument design language with an indigo
accent and reticle glyph, served via faithfully-copied theme assets, with a drift guard,
and no change to data, detector, report, or eval behaviour.

Success criteria:
1. Every page serves the Instrument shell: `<body class="ins" data-app="sprintsight">`, the
   `.topbar`, the `.band` (with the oscilloscope `.waves` mount), `<main class="page">`, and
   the `.footer`; head links `/css/instrument-core.css` then `/css/sprintsight.css` and loads
   `/js/oscilloscope.js` as a module.
2. The watermelon meaning still renders correctly (served-markup tests: Atlas flagged red,
   Echo insufficient-evidence), and all existing data/behaviour web tests pass (logic
   unchanged); tests that pinned the OLD markup/classes are updated to the new ones.
3. A drift-guard test SHA-compares the copied unchanged theme files against
   `/var/www/suite/shared/theme/` and fails on divergence; it SKIPS when the suite source is
   absent (so Sprintsight CI stays independent).
4. The indigo accent and reticle glyph appear in the chrome; the red/amber/green verdict
   colours remain a separate, unambiguous set.
5. `pytest -q` green, ruff clean, deterministic eval gates unchanged.

## Scope

In scope:
- Vendor the Instrument assets (css, js, glyphs, 8 fonts) into Sprintsight and serve them at
  web-root paths.
- Replace `base.html` with the Instrument shell; add `data-app="sprintsight"`.
- New `sprintsight.css` (per-app tokens + indigo accent + watermelon RAG set + Sprintsight
  components).
- Reskin all five content templates onto Instrument components.
- The reticle glyph as a separate SVG referenced by the brand mark.
- A drift-guard test; updates to existing web tests that assert old markup.
- Remove the superseded `static/app.css`.

Out of scope (deferred):
- Enforcing a Content-Security-Policy header (Sprintsight will be CSP-clean since no inline
  styles/scripts, but turning the header on is its own security slice).
- Dark mode (the suite has none).
- Registering Sprintsight as a formal suite surface in the suite's Node sync/drift tooling
  (the "full member" path; revisit if Sprintsight becomes a permanent suite product).
- Folding the reticle into the suite's shared `glyphs.svg` (only relevant under full
  registration).

## Design

### 1. Vendor + serve the theme assets

Copy unchanged into `sprintsight/web/static/theme/` mirroring the suite layout:
`css/instrument-core.css`, `js/oscilloscope.js`, `illos/glyphs.svg`, `fonts/<8>.woff2`.
Add FastAPI mounts so they are served at the web-root paths Instrument expects:
`/css`, `/js`, `/illos`, `/fonts` -> the matching subdirs. `sprintsight.css` is authored by
us and also served from `/css/sprintsight.css`. (Exact mount mechanics pinned in the plan;
the principle is byte-identical files at the same URLs the suite uses.)

### 2. The page shell (`base.html`)

Rebuild to the Instrument structure:
- `<body class="ins" data-app="sprintsight">`.
- `.topbar`: `.brand` = reticle mark (`<svg class="mk"><use href="/illos/sprintsight.svg#glyph-sprintsight"/></svg>` + "Sprintsight") + `.tbacts` holding the session controls as `.btn .btn-ghost .btn-sm` (user email/role + Sign out, or Sign in).
- `.band` hero: a `.waves` div (oscilloscope mount) + `.band-in` with `.eyebrow`, `<h1>`, `.sub`, each fed by Jinja blocks per page.
- `<main class="page">{% block main %}{% endblock %}</main>`.
- `.footer` "Sprintsight".
- `<head>`: `<link rel="stylesheet" href="/css/instrument-core.css">`, then
  `<link rel="stylesheet" href="/css/sprintsight.css">`, then
  `<script type="module" src="/js/oscilloscope.js"></script>`.

### 3. `sprintsight.css` (per-app stylesheet)

Authored at `sprintsight/web/static/theme/css/sprintsight.css`, following the signal/raid
per-app pattern:
- Spacing `--s-*`, radius `--r-*`, shadow `--shadow-*` tokens with the suite's identical values.
- Indigo accent on `.ins[data-app="sprintsight"]`, starting values (to confirm against WCAG AA
  for white-on-accent during build): `--accent: oklch(0.50 0.10 262)`,
  `--accent-deep: oklch(0.42 0.10 262)`, `--accent-soft-wash: oklch(0.95 0.03 262)`. White text
  on `--accent` at L0.50 is expected to pass AA (unlike amber); confirm in build.
- A dedicated verdict set kept separate from the accent: `--rag-red`, `--rag-amber`,
  `--rag-green` (vivid, for the verdict banner, the watermelon pills, and the portfolio grid),
  plus washes. The watermelon "reported vs actual" semantics own these; the indigo accent never
  uses them.
- Sprintsight components mapped onto Instrument primitives: the verdict banner, the watermelon
  portfolio grid (cards), the audience tabs, the report sections (cards), the evidence/citation
  list, and the live-DB panel.

### 4. Per-page reskin

Rework each content block onto Instrument components, data and routes unchanged:
- `login.html`: a centred `.card` within the band (simple; not the hub's bespoke gradient authcard).
- `portfolio.html`: the watermelon grid as Instrument cards + RAG verdict pills + a summary band.
- `team.html`: verdict banner + audience tabs + report cards + evidence list + the live-DB panel.
- `crosstool.html`: the cross-tool watermelon + stalled lists + the mode badge, as cards/pills.
- `admin_accounts.html`: an Instrument `.table` + form.

### 5. The reticle glyph

Draw `<symbol id="glyph-sprintsight">` (circle + crosshair + centre dot) in the suite's glyph
style (consistent viewBox, `currentColor` strokes, matching weight) as a SEPARATE file
`sprintsight/web/static/theme/illos/sprintsight.svg`, referenced by the brand mark. The suite's
copied `glyphs.svg` stays byte-identical so it remains drift-checkable.

### 6. Drift guard

`tests/web/test_theme_drift.py`: SHA-256 compare each copied unchanged asset
(`instrument-core.css`, `oscilloscope.js`, `glyphs.svg`, the 8 fonts) against
`/var/www/suite/shared/theme/`. Fail with a "re-sync from the suite" message on any mismatch.
SKIP the whole test when the suite source path is absent, so Sprintsight CI (which has no suite
checkout) stays green and independent. `sprintsight.css` and `sprintsight.svg` are OURS and are
not drift-checked.

### 7. Testing (eval = served markup, not pixels)

Per the project convention, tests assert served HTML, not screenshots:
- New `tests/web/test_theme.py`: each page serves `body.ins[data-app="sprintsight"]`, the
  `.topbar`/`.band`/`.page` structure, and the two theme stylesheet links.
- Reuse/extend existing web tests to confirm the watermelon meaning still renders (Atlas red,
  Echo insufficient) under the new markup.
- Update existing web tests that asserted the OLD markup/classes (e.g. `.app-header`) to the new
  Instrument classes. No service/detector/report/eval code changes, so those suites stay green.
- The drift guard (Section 6).

## Risks and mitigations

- **Existing tests pin old markup:** expected churn; update them to the new classes as part of
  the slice (they assert structure, not behaviour).
- **Asset URL mismatch (the /static vs web-root trap):** mitigated by serving the theme at the
  exact web-root paths Instrument's absolute `url()`/`href`s expect; a smoke test loads a page
  and asserts the asset links resolve to 200.
- **Accent contrast (AA):** indigo starting values confirmed against AA for white-on-accent
  during build; adjust lightness if needed (the RAID amber precedent shows the suite handles
  this with `--accent-deep`/`--accent-btn`).
- **Drift guard coupling to an absolute path:** mitigated by skip-when-absent so CI is unaffected.

## Learning queue flag (HANDOVER)

New concept for a non-engineer: "adopting a shared design system by faithful copy + a drift
guard" — Sprintsight now wears the suite's Instrument skin (one shared stylesheet, fonts, icon
sprite, signature animation), kept in step by a test that flags any divergence from the suite
source, without entangling the Python app in the suite's Node build tooling. Flag one line in
the HANDOVER Learning queue at build time.
