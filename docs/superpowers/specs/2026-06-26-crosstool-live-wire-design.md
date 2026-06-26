# Cross-tool live-wire design (SS-5, Stage 7 follow-on)

Date: 2026-06-26
Status: approved design, pre-implementation

## Plain-English summary (read this first)

Today the `/crosstool` web page reads two frozen files (a saved snapshot of a Jira board and a
saved snapshot of a GitHub repo). It reconciles them and shows the cross-tool watermelons and the
amber stalled signal. It is fully offline and deterministic.

This change adds a switch. When the switch is on AND real credentials are present, the page instead
reads the LIVE Jira board and LIVE GitHub repo, reconciles them the same way, and shows the result
with a small "live as of <time>" badge. When the switch is off (the default, and always in CI),
nothing changes at all. Live data can never sneak into a normal page load.

The cross-tool watermelon detector already works live from the command line. This change makes it
work live inside the actual product, not just the CLI. That is the whole point: the strongest moat
feature, end-to-end, in the web app.

## Why this is small

The live CLI path and the offline web path both end up producing the SAME two things before they
reconcile, just from different sources:

- a dict of tickets shaped `{key, status, team}`
- a dict of GitHub activity keyed by ticket key (`dict[str, Activity]`)

So the feature is only: let the web page source those two things from the live connectors instead of
the frozen files, behind a fail-safe gate. Everything downstream (the pure `reconcile()`, the row
shaping, the both-tool citations, the HTML template) is untouched.

## Architecture

### The seam (the one real design choice)

`crosstool_view()` gains an injectable **source**: a callable that returns a tuple
`(tickets, activity, as_of, mode)`, where `mode` is one of `"live"`, `"offline"`, or
`"offline-failed"`.

- `_offline_source()` returns the fixture tickets + fixture activity + the pinned
  `CROSSTOOL_AS_OF` + `mode="offline"`. Byte-for-byte the same behaviour as today.
- `_live_source()` returns tickets from `JiraConnector`, activity from `GitHubConnector`, and
  `as_of = datetime.now(UTC).isoformat()` + `mode="live"`.
- `_active_source()` picks live when the gate is open, else offline. It also owns the honest-failure
  fallback (see below).
- `crosstool_view(source=_active_source)` so tests inject a fake source with no network.

This mirrors the existing `_writer` / `_active_writer()` seam in `service.py`.

### The fail-safe gate

`_crosstool_live_enabled()` is true ONLY when all of these hold:

- `SPRINTSIGHT_CROSSTOOL_LIVE == "on"`
- a real `GITHUB_TOKEN` is present
- a Composio key is present (Jira live read needs it)
- a repo is configured: `SPRINTSIGHT_CROSSTOOL_REPO` (e.g. `owner/name`)
- a project is configured: `SPRINTSIGHT_CROSSTOOL_PROJECT` (e.g. `SSSB`)

Any missing piece falls back to offline. Default and CI: off. Same shape as `_llm_enabled()`.

### Honest failure (demo safety)

If the gate is open but the live read throws (network, auth, rate limit), the page does NOT return a
500 and does NOT silently show stale offline data dressed up as live. Instead `_active_source()`
catches the error, falls back to the offline replay, and returns `mode="offline-failed"`, which the
template renders as "offline (live read failed)". Faithful reporting beats a pretty page that lies.
Surfacing "live failed" is more useful in a live demo than a blank or a fake-green.

### Shared ticket extraction (small refactor)

`_tickets_from_artifacts()` currently lives inside `scripts/run_cross_tool.py`, which the web layer
cannot import (scripts are not a package). Lift it into the `connect` package (e.g.
`sprintsight/connect/jira_tickets.py`) so both the CLI and the web use one copy. No behaviour change;
the CLI imports it from the new home.

### The `live` badge

Add a `mode: str` field to `CrossToolSummary` (one of `"live"`, `"offline"`, `"offline-failed"`) so
the template can show a small badge: "live as of <time>", "offline replay", or "offline (live read
failed)". A `live` boolean is derivable as `mode == "live"` if the template prefers it. This is the
only piece that is more than plumbing. It is what makes a live demo legible.

## Data flow

1. Request hits `GET /crosstool` (or `/api/crosstool`).
2. `crosstool_view()` calls its `source` (default `_active_source`).
3. `_active_source()` checks the gate. Open -> `_live_source()` (live connectors, real clock).
   Closed -> `_offline_source()` (fixtures, pinned clock). Live error -> offline with `offline-failed`.
4. The source returns `(tickets, activity, as_of, mode)`.
5. `crosstool_view()` reconciles each ticket against its activity (unchanged), shapes rows + the
   summary (now carrying `live`), sorts flagged-first.
6. The page/API renders. Live calls only ever happen inside step 3 and only when the gate is open.

## Error handling

- Live read failure: caught in `_active_source()`, fall back to offline replay, mark `live=False`
  with the failed state. Never a 500 from a live problem.
- Misconfiguration (flag on but a credential or repo/project missing): the gate reads as closed, so
  the page serves offline. No crash.
- The offline path has no new failure modes; it is the existing code.

## Testing (eval-first, red first)

Convention for this project: test the served data, not the pixels, and test the contract a seam's
swap must honour.

Red-first tests:

1. **Live shaping via a fake source.** Inject a fake `source` returning live-shaped tickets +
   activity (no network). Assert `crosstool_view` shapes the page correctly: summary counts, rows,
   both-tool citations, and `summary.mode == "live"`. This is the new behaviour and fails before the
   seam exists.
2. **Gate off by default.** With no env set, assert `crosstool_view()` serves the offline replay
   unchanged (same counts/rows as today, `summary.mode == "offline"`).
3. **Honest failure.** Inject a source whose live branch raises; assert the page falls back to
   offline and reports `summary.mode == "offline-failed"` rather than raising.

No live API call in CI. The live connector paths stay key-gated and unexercised by the suite, exactly
like the LLM-writer slice. Existing crosstool tests, the deterministic eval gates (watermelon 4/4,
report 4/4), and the cross-tool eval (7/7) must all stay green.

## Out of scope (YAGNI)

- Per-team rollup of cross-tool findings.
- Caching the live read (each gated request reads live; fine for a demo).
- Configuring repo/project from the UI (env-driven only).
- Real secrets management / `.env` autoloader (still deferred, tracked in the open-wiring memory).

## Files touched (anticipated)

- `sprintsight/web/crosstool_service.py` — the source seam, gate, honest-failure fallback, `live`
  on the summary.
- `sprintsight/connect/jira_tickets.py` — new home for the shared ticket extraction.
- `scripts/run_cross_tool.py` — import the extraction from its new home.
- `sprintsight/web/templates/crosstool.html` — the small live/offline badge.
- `tests/web/test_crosstool_service.py` (and/or a new test module) — the three red-first tests.
