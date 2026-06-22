# Design: switch the web app onto the real AI report-writer

Status: approved (David, 2026-06-22). Stage 6, Epic SS-6. Branch: `stage6-web-llm-writer`.

## Plain-English summary (read this first)

Today the website is fully offline. The drill-in page shows reports written by `compose`,
a deterministic stand-in that never calls the AI. This slice lets the website show real
AI-written reports, but only when we deliberately turn the brain on with an environment flag.
With the flag off (the default), nothing changes: the site stays offline and the tests stay
deterministic. We also add a small in-memory cache so we are not paying for the same report
over and over when someone clicks between audiences.

The plumbing is almost free. The AI writer already exists behind a seam from Stage 2, and it
is already swap-compatible with `compose`. The real work is the gate (when to use it), the
cache (so it is not slow or costly), and the eval-first tests that prove the served contract.

## Goal

When deliberately enabled, the drill-in page (`/team/{id}`) shows real AI-written,
audience-tuned reports. When not enabled, the offline behaviour is unchanged.

## Decisions (settled in brainstorming)

1. Trigger: explicit opt-in flag. Fail-safe by default.
2. Caching: simple in-memory cache, keyed by team and audience. No database.

## How it works

### 1. The trigger (gating)
A new environment flag, `SPRINTSIGHT_WEB_LLM`. The web app uses the AI writer only when:
- `SPRINTSIGHT_WEB_LLM` is `on`, AND
- a real Anthropic API key is present in the environment.

If the flag is off (default), or on but no key exists, the app falls back to `compose`.
Offline and CI stay green and deterministic with zero config. This mirrors the auth slice's
fail-safe gating (`SPRINTSIGHT_ENV` precedent).

"Key present" is defined concretely: `ANTHROPIC_API_KEY` is set, starts with `sk-ant-`, and is
longer than 50 characters. This reuses the same key shape already used by the live skip-guard in
`tests/test_llm_writer.py`, so the web gate and the existing live tests agree on what a real key
looks like. A blank or obviously-fake key does not open the gate.

### 2. How the writer is chosen
A small resolver in `sprintsight/web/service.py` returns `make_llm_writer()` when the gate is
open, else `compose`. The existing module-level `_writer` seam stays as the injection point
(default `compose`), so tests can still swap in a fake writer directly. No routes or templates
change. They keep calling the service.

### 3. Caching
An in-memory dictionary keyed by `(team_id, audience)` maps to the computed `Report`. The first
request for a combination computes the report through the active writer; repeat loads and
audience switches serve from the cache. It clears on process restart. No database, no new
persisted data. Acceptable because the demo data is static.

### 4. Failure behaviour (all reused, none new)
- Flag on but key missing: the resolver never attempts a call; it returns `compose`.
- Call fails mid-request: the LLM writer already falls back to `compose` prose per section.
- A section breaks the rules (ticket IDs leak, over the word cap): that section already reverts
  to `compose`.

### 5. The served contract is unchanged
Same `Report` shape, same sections per audience profile, same sources-from-claims, same
"not enough evidence" flag. The UI looks identical; only the prose inside the sections improves
when the brain is on. Model stays `claude-sonnet-4-6` (the writer that cleared both audiences in
the readability arc). No model change in this slice.

## Eval-first: what we test (the contract, not pixels)

1. Default-offline: with the flag unset, the served report for a team equals the deterministic
   `compose` output, and no network call is attempted.
2. Selection: flag on plus key present resolves to the AI writer; flag on plus no key resolves
   to `compose` (fail-safe). Tested with an injected fake writer, so no live call in CI.
3. Cache hit: two requests for the same team and audience invoke the underlying writer only once
   (asserted with a counting writer).
4. Cache key separation: different audiences for the same team are cached separately.
5. Existing LLM-writer fallback and thin-data tests already cover rule-violations and the Echo
   insufficient case. We lean on those rather than duplicate them.

## Security note (flagged per build rule)

This turns on real external API calls from the web app for the first time. It is off by default,
key-gated, runs on the Zero-Data-Retention path like our other Anthropic traffic, and persists
nothing new (the cache is in-memory and ephemeral). Recorded in HANDOVER; one line added to the
HANDOVER learning queue, since "the web app now makes live AI calls" is a genuinely new concept.

## Out of scope (staying lean)

- No persistent storage.
- No cache invalidation or time-to-live.
- No per-request model selection.
- No streaming.

These stay deferred with the rest of the real-wiring backlog.
