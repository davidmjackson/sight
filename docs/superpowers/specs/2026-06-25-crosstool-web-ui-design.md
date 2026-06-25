# Cross-tool watermelons + stalled signal in the web UI — design

Date: 2026-06-25
Stage: 7 (Epic SS-5), final feature slice
Status: approved (David, 2026-06-25), ready for implementation plan

## Plain-English summary (read this first)

We built a cross-tool watermelon detector: it reads real Jira tickets and a real GitHub
repo and flags the per-ticket lie where Jira says "progressing" but GitHub shows no real
work, plus an amber "this PR has stalled" warning. Today that only shows up in the demo
script and the eval harness. A person using the web app cannot see it.

This slice puts it on screen. We add one new page, `/crosstool`, that lists every checked
ticket with a red (watermelon), amber (stalled), or clean verdict, citing both Jira and
GitHub. It reads captured replay files only (no network, no live credentials, nothing to
gate). It changes no existing behaviour: the burndown detector, the 5-team portfolio, and
every eval gate stay exactly as they are.

## Context: the two data worlds (why this is a new page, not a new row)

The web app today shows 5 synthetic teams (Atlas, Boreas, Cygnus, Draco, Echo). Their
watermelon is "burndown chart vs status report," computed from the synthetic corpus by the
burndown detector behind `sprintsight/web/service.py`.

The cross-tool watermelon is a different world: its unit is a Jira *ticket* (SSSB-1,
SSSB-2, ...), and its source is captured replay of the live SSSB board + the
sprintsight-sandbox GitHub repo. The reconciler (`sprintsight/crosstool.py`) compares one
ticket's Jira status against its GitHub activity (joined by the Jira key in branch/PR/commit
text) and returns the existing `Verdict`.

Because the unit and the source differ, the cross-tool view is a dedicated page, not a row
on the 5-team grid.

## Decisions (locked during brainstorming)

1. **Placement:** new dedicated page `/crosstool`, linked from the portfolio home page.
2. **Page content:** a summary band (counts) above a flagged-first list. Red and amber
   tickets sort to the top; clean tickets show muted below. Each row cites both tools.
3. **Data source:** offline replay only. The page always reads captured fixtures. No live
   read, no network in a web request, no env/credential gate. Live reads stay in the CLI
   demo (`scripts/run_cross_tool.py`) where they already work.
4. **Demo data:** add one stalled (amber) ticket to a web-demo fixture pair so the page
   shows all three colours. The existing captured pairs produce only red + green (amber
   never fires in them), so the stalled half of the slice would otherwise be invisible.
5. **Structure:** a new module `sprintsight/web/crosstool_service.py` beside `service.py`,
   so the two data worlds stay unmixed.

## Architecture

### Component 1: `sprintsight/web/crosstool_service.py` (new, pure data layer)

One shaping function and small frozen view-models. No network, no `datetime.now`.

- `CROSSTOOL_AS_OF: str` — a pinned ISO timestamp constant. The reconciler's stalled
  check measures PR quietness against this, so the amber case fires deterministically on
  every run. (Mirrors how the portfolio "judges as-of Sprint 15.")
- View-models (frozen dataclasses):
  - `CrossToolSummary(checked: int, watermelons: int, stalled: int, as_of: str)`
  - `CrossToolRow(key, team, reported_status, actual_status, classification, headline,
    jira_citation, github_citation)` where `classification` is one of
    `"watermelon" | "stalled" | "clean"`.
  - `CrossToolPage(summary: CrossToolSummary, rows: list[CrossToolRow])`
- `crosstool_view(as_of: str = CROSSTOOL_AS_OF) -> CrossToolPage`:
  1. Load the two captured web fixtures via the existing `RecordedGitHubConnector` and a
     plain JSON read for the Jira tickets (same ticket shape the demo builds:
     `{key, status, team}`).
  2. For each `(key, ticket)`, call the existing `reconcile({...})` with `as_of` and the
     ticket's `Activity`. Pairing the key with its verdict is done here (the web layer
     iterates tickets and calls `reconcile` directly, so each row keeps its ticket key;
     `Verdict` itself carries no key field).
  3. Derive `classification`: `watermelon` if `verdict.is_watermelon`, else `stalled` if
     `verdict.actual_status == "amber"`, else `clean`.
  4. Build the two plain-English citations from the verdict's evidence/signal tokens (see
     Component 2).
  5. Sort rows: watermelon, then stalled, then clean (stable within a group, by key).
  6. Fold the summary counts from the rows (pure, like `service.summarize`).

### Component 2: plain-English citation mapping (pure helper in the same module)

Translate the raw evidence/signal tokens into readable citations so the page reads like
prose, not log lines:

- `jira-SSSB-1` + ticket status -> `"Jira SSSB-1 (In Progress)"`.
- `github:no-ref:SSSB-1` -> `"GitHub: no linked branch, PR, or commit"`.
- `github:PR#12:open-unmerged` -> `"GitHub: PR #12 is open and unmerged"`.
- `github:no-merged-pr:KEY` -> `"GitHub: work exists but nothing merged"`.
- `github:PR#1:stalled-12d` -> `"GitHub: PR #1 has had no activity for 12 days"`.
- `github:active:KEY` -> `"GitHub: active, linked work found"`.
- `github:n/a:KEY` -> `"GitHub: ticket not claiming progress"`.

This mapping is a pure function of the token string, which makes it a clean, deterministic
test target. Deep links to the actual PR URL are out of scope for this slice (the `Verdict`
does not carry the URL); citations are readable text, consistent with the existing
portfolio/team evidence display.

### Component 3: route + API + template (`sprintsight/web/app.py`, templates, static)

- `GET /crosstool` (auth-gated, same `session_user` redirect-to-login as other pages) —
  renders `crosstool.html` with the `CrossToolPage`.
- `GET /api/crosstool` (`require_api_user`) — returns the `CrossToolPage` as JSON, mirroring
  `/api/portfolio`. Gives the served-contract test a clean endpoint and keeps API symmetry.
- `crosstool.html` extends `base.html`, reuses the existing design-system CSS (summary band
  + verdict cards/rows). Colour by classification: red = watermelon, amber = stalled,
  green/muted = clean.
- Add a nav link to `/crosstool` from `portfolio.html` so the page is reachable.

### Component 4: web-demo fixtures (`data/captured/`)

A new pair, e.g. `crosstool_web_jira.json` + `crosstool_web_github.json`, based on the
existing demo pair, with one added ticket that produces amber:

- a ticket with status **In Progress**, that **has** an open PR, whose PR `updated_at` (and
  any commit) is older than the stalled threshold (default 7 days) relative to
  `CROSSTOOL_AS_OF`.

Target on-screen result: at least one watermelon, one stalled, one clean.

## Data flow

```
captured web fixtures (JSON)
  -> RecordedGitHubConnector.fetch_activity()  +  Jira tickets {key,status,team}
  -> reconcile(ticket, activity, as_of=CROSSTOOL_AS_OF)   [existing, unchanged]
  -> CrossToolRow per ticket (classification + plain-English citations)
  -> sort flagged-first + fold CrossToolSummary
  -> CrossToolPage
  -> /crosstool (HTML)  and  /api/crosstool (JSON)
```

## Eval-first plan (what is written before the code)

Per the project rule "test the served data, not pixels," the first commit is a failing
served-contract test (`tests/`), red before `crosstool_service.py` exists, asserting against
the web fixtures:

1. `CrossToolSummary` counts are correct (e.g. 2 watermelons, 1 stalled, N checked).
2. Each ticket's `classification` is correct (watermelon / stalled / clean).
3. Rows are ordered flagged-first (watermelon, then stalled, then clean).
4. Each flagged row's citations name **both** Jira and GitHub, in plain English.
5. The amber row's GitHub citation reflects the stalled PR (the regression guard for the
   thing the fixtures previously could not show).

Runs fully offline, no API call. The `/api/crosstool` JSON contract may be asserted via the
shaping function directly and/or a FastAPI TestClient call.

## What stays untouched (no regressions)

- The burndown detector and `sprintsight/web/service.py` (5-team world).
- The watermelon eval (4/4) and report-quality eval (4/4) CI gates.
- The existing cross-tool eval (7/7) and `sprintsight/crosstool.py` reconciler logic.
- `scripts/run_cross_tool.py` live + replay demo paths.

## Out of scope (YAGNI for this slice)

- Live Jira/GitHub reads from the web request (stays CLI-only).
- Deep links to PR/issue URLs (no URL on the `Verdict`; readable text citations instead).
- Per-team rollups, filtering, pagination, or board-size scaling beyond the demo.
- Any write-back to Jira or GitHub (the reconciler is recommend-only by design).

## Jira

New Story under Epic SS-5 (cross-tool). Eval-first: served-contract test red -> green, page
added, docs updated, then In Review -> Done.
