# Sprintsight — HANDOVER

Living cross-session handover. Read this first when starting a new thread or agent.
Last updated: 2026-06-27 (Claude Code session 21: REAL-WIRING SLICE 2 — REAL EMBEDDER (decision D1) DONE + MERGED to main @ 0954a9a + LIVE-VERIFIED. Swapped the fake `HashingEmbedder` (matches only identical words) for a real, self-hostable, in-region 1024-dim model (`thenlper/gte-large`) via new `LocalEmbedder` + `make_embedder()` factory in `sprintsight/ingest/embedding.py`, selected by env `SPRINTSIGHT_EMBEDDER=local` (offline `HashingEmbedder` stays the default, so CI + the LangGraph builder + the web/connector demos are unchanged). `sentence-transformers` lives in a new lazy `[embed]` pyproject extra; the schema is UNTOUCHED (`chunk.embedding vector(1024)`). The ingest + retrieve scripts both call the factory so ingest and query always use the same embedder. KEY FIX from the independent review (the blocker): the ingest dedup hash now folds in the embedder identity (`embedder_signature` -> `pipeline._content_hash`), so switching the embedder against an already-populated store (the slice-1 Supabase, loaded with the fake) RE-EMBEDS every artifact instead of silently skipping it on an unchanged body and leaving stale, incomparable vectors. Eval-first: new `tests/test_embedder_real.py` (semantic-vs-lexical paraphrase recall; CI baseline pinned <=0.25, the real-model leg gated/skipped) + a re-embed test in `tests/test_ingest.py`. LIVE-VERIFIED: real model clears paraphrase recall >=0.75 vs the stand-in's 0.25. Independent whole-branch review = blocker found, fixed, re-verified CLOSED, Ready to merge. Full suite 265 passed + 4 skipped, ruff clean; deterministic eval gates unchanged. Runbook: docs/embedder/real-embedder.md; spec/plan: docs/superpowers/{specs,plans}/2026-06-27-real-embedder*. NOTE: the real model is wired + eval-proven, but re-embedding the live Supabase end-to-end is a separate operator step (run the runbook; first re-ingest re-embeds all 37 even with the same stand-in because the hash FORMAT changed — a harmless one-time refresh). EARLIER session 20: SECURITY HARDENING — migration `db/migrations/0002_enable_rls.sql` enables Row Level Security (no policies) on all 8 public tables, clearing the Supabase Security Advisor "RLS not enabled" findings; safe because the `postgres` owner role bypasses RLS and Sprintsight never uses the PostgREST public API (anon key), verified live via `retrieve_smoke.py`; the live instance was fixed by pasting the 8 `enable row level security` statements into the Supabase SQL editor (migrate.py is not re-runnable); per-tenant `tenant_id` policies deferred to the real-auth slice; merged to main @ 8da61f5, tests 261 passed + 3 skipped unchanged. EARLIER session 18: STAGE 7 COMPOSIO SDK PORT slice complete and MERGED to main — the live Jira connector (`sprintsight/connect/connector.py:fetch_issues`) was ported from the removed `ComposioToolSet().execute_action(...)` API to the current `composio==0.16` `Composio().tools.execute(...)` client, identifying the connected account via a new env var `COMPOSIO_CONNECTED_ACCOUNT_ID`; the `/crosstool` live gate now also requires that id so the offline/live badge stays honest; `composio` pinned `>=0.16,<0.17`. Built subagent-driven, 4 tasks each reviewed clean + opus whole-branch review = Ready to merge, 0 Critical/Important (2 Minors applied). Full suite 245 passed + 3 skipped, ruff clean; eval gates 4/4 + 4/4 + cross-tool 7/7 unchanged. LIVE-VERIFIED end to end (2026-06-26, @ a22eb0c): a real human-run read of SSSB returned 6 tickets (top cited SSSB-1). Three composio-0.16 quirks were fixed live: plain-dict response (read dict-first), required `user_id`/`COMPOSIO_USER_ID` alongside `connected_account_id` (gate now needs SEVEN vars), and `dangerously_skip_version_check=True`. docs/connectors/live-run.md documents all three env vars + the editable-install requirement. UPDATE (session 19, 2026-06-26): the full `/crosstool` WEB live demo is now DONE + LIVE-VERIFIED. A logged-in web request read the real SSSB board + the real sprintsight-sandbox repo live behind the seven-var gate; badge showed `live as of 2026-06-26T07:50:02Z` and flagged the two cross-tool watermelons (Atlas/SSSB-1 no-ref, Boreas/SSSB-2 PR#1 open-unmerged), agreeing exactly with the CLI read. No new code; verification only. Prior session 17: STAGE 7 cross-tool LIVE-WIRE slice complete and MERGED to main — the `/crosstool` page can now read the LIVE Jira board + GitHub repo behind a fail-safe gate (`SPRINTSIGHT_CROSSTOOL_LIVE`=on + GITHUB_TOKEN + Composio key + repo/project), offline-by-default and deterministic in CI; a live failure falls back to the offline replay and says so ("offline (live read failed)"), never a 500 and never fake-live. See "Where we are" below. Prior: STAGE 6 first slice (Portfolio + Watermelon UI, Epic SS-6) on branch `stage6-watermelon-ui`. Prior: STAGE 4 (Observability + Evals, Epic SS-7, Story SS-30) complete on branch `stage4-observability-llm-judge`. LLM-as-judge readability scorer added (`sprintsight/evals/judge.py`): four prose dimensions (clarity, audience_fit, coherence, actionability), injected grader (fake in CI, real Anthropic on the key-gated path), advisory pass bar (every dim >= 3, mean >= 4, non-gating). Calibration meta-eval added (`sprintsight/evals/calibration.py`): grades the judge against hand-labelled good/bad anchor reports before it becomes a gate. Per-node graph tracing added to `sprintsight/graph/builder.py` via optional Tracer (no-op default, CI stays offline; one `graph:run` span wraps the run, each node emits a `node:<name>` span). ADR-0003 records the tracing design. Opt-in `--judge` flag on `scripts/run_report_eval.py` runs the readability pass (advisory, never changes exit code). `scripts/run_calibration.py` runs the live calibration. Both new modules green in CI with fakes; live paths key-gated. Deterministic watermelon + report evals unchanged, still the CI gate. Prior: STAGE 3 DONE (SS-29, branch stage3-langgraph-graph); STAGE 2 DONE (arc 2, 374bf6c); STAGE 0 + STAGE 1 CLOSED. Repo on github.com/davidmjackson/sight; CI green. System of record: Jira (statuses) + the docs below (specs/decisions). FOLLOW-UP THIS SESSION (2026-06-19): writer-readability arc on branch `writer-readability-arc` (see the dedicated section below).

## Who reads what
- This file (HANDOVER.md): shared current state. BOTH the planning thread and Claude Code read it. One state file on purpose; do not fork it.
- Claude Code (building): also read CLAUDE.md for build conventions and how to drive the Jira board.
- Planning thread (Claude Desktop/web): operating manual is the Project instructions + sprintsight-braindump.md.
- docs/ specs are shared by both. Principles live in the brain dump, state lives here, build conventions live in CLAUDE.md. Each fact has one home.

## Learning queue (training thread consumes these)
Ownership: training (LEARNING-LOG.md) is the planning thread's; development is Claude Code's.
LEARNING-LOG.md has ONE writer: the planning/training thread. Do not edit it from Claude Code.
When a Story introduces a genuinely new concept a non-engineer would need explained, Claude Code
APPENDS one line below. Flag only, do not teach. The training thread turns each flag into a
LEARNING-LOG entry (with David's restatement) and deletes the line once that entry is committed.
Format per item: concept | one line on what is new | code/stage pointer | date flagged.

- Correcting a quality bar that demands fabrication | when the readability judge wanted owners/dates/decisions our no-fabrication rule forbids inventing, we corrected the rubric (not the facts, not the bar), guarded by the calibration meta-eval | sprintsight/evals/judge.py (actionability) + scripts/run_calibration.py + writer-readability arc | flagged 2026-06-19
- De-noising an LLM judge with a median | a single LLM-judge run wobbles run to run (exec swung 4.2 to 2.75 with no code change), so we sample it 3 times and take the median; a noisy judge cannot be a CI gate yet | sprintsight/evals/judge.py sample_judge + scripts/run_report_eval.py --judge | flagged 2026-06-19
- When a measurement reveals a bug, not a quality gap | the LLM exec prose was rejected because the mechanics filter matched "points" as a substring (catching its own "watch-points"); the fix was a correct boundary matcher, not prose-tweaking; lesson = read why a score is low before changing the writer | sprintsight/report/audience.py contains_mechanics + llm-writer-readability arc | flagged 2026-06-19
- An LLM gate that can disqualify itself | the judge gate runs its own calibration meta-eval first; a judge that fails calibration is not trusted to block the build, so a flaky or misconfigured judge cannot turn CI red | scripts/run_report_eval.py `_run_judge_gate` + sprintsight/evals/judge.py `judge_gate_decision` + judge-gate-arc | flagged 2026-06-21
- An "eval" for a UI tests the served data, not the pixels | Stage 6's first screen stays eval-first by asserting the FastAPI service/JSON output matches the watermelon ground truth (Atlas flagged red, Echo insufficient-evidence), with light HTML smoke tests, instead of screenshot testing | sprintsight/web/service.py + tests/web/ | flagged 2026-06-21
- An auth seam + session cookie (faking the identity provider offline) | we put a login in front of the web app, but instead of wiring real Supabase we built an Authenticator seam with a local SeedAuthenticator stand-in (same trick as faking the DB and the embedder), and the logged-in identity rides in a signed session cookie; the real provider is a deferred stub behind the same interface | sprintsight/web/auth/ (users.py seam, session.py cookie, hashing.py) | flagged 2026-06-22
- Audience-tuned reporting, now switchable in the UI | the same team's data becomes three different reports (exec, programme, team) shaped for each reader; the drill-in page now shows the report with three links to switch audience, and a cited Sources list makes the "fully-cited" promise visible | sprintsight/web/service.py + sprintsight/web/templates/team.html | flagged 2026-06-22
- web live-LLM gate | the web app can now make real AI calls, switched on only by an env flag plus a real key (fail-safe, offline by default) | sprintsight/web/service.py _llm_enabled | 2026-06-22
- A design system / design tokens | the app's look now lives in named CSS variables (one place to change a color or spacing) instead of being repeated across templates; this is what makes a UI consistent and quick to restyle | sprintsight/web/static/app.css :root tokens + stage7-ux-polish slice | flagged 2026-06-22
- First real external-tool connector (Jira), behind a seam | the app can now read a live Jira board and turn each ticket into the same Artifact shape the synthetic corpus uses; the network-touching fetch is walled off in one function, the real logic is a pure translator, and an offline RecordedConnector twin lets every test run without a network | sprintsight/connect/ + stage7 Jira-connector slice | flagged 2026-06-24
- Cross-tool reconciliation (the watermelon that needs two tools) | the first watermelon that no single tool can see: we join a live Jira ticket to its GitHub work by the ticket key and flag "Jira says progressing, GitHub shows no work / an unmerged PR"; the join is a factual key match, not a fuzzy text search, so it sits in a small new reconciler beside the old detector, not inside it | sprintsight/crosstool.py + sprintsight/connect/github.py + Goal B slice | flagged 2026-06-25
- Amber tier + an injected clock for staleness | we added a third verdict colour (amber = "PR parked") that depends on the current time, but a pure function can't call the clock and stay testable, so the reference "now" is passed IN (as_of) rather than read from the system; same injected-seam trick as the fake DB/embedder | sprintsight/crosstool.py _stalled + stalled-signal slice | flagged 2026-06-25
- The moat feature now runs LIVE inside the product, not just the CLI | the cross-tool watermelon detector could already read live Jira+GitHub from the command line; the `/crosstool` web page now does the same behind the same fail-safe gate we have reused four times (offline by default, live only when a flag plus real credentials are set), and an honest badge shows whether you are looking at live data, the saved replay, or a failed-live fallback | sprintsight/web/crosstool_service.py _active_source/_crosstool_live_enabled + crosstool-live-wire slice | flagged 2026-06-26
- SDK version drift | code written against an old third-party SDK breaks when a newer rewritten version installs; fix is to target + pin the current API | sprintsight/connect/connector.py + 2026-06-26 | 2026-06-26
- Going live is a config + credentials act, not new code | the cross-tool watermelon was already live-capable in the web app; the session-19 demo proved that flipping it from the saved snapshot to real two-tool data is purely a matter of supplying the seven-var credential gate (in one terminal) and logging in, with an honest "live as of ..." badge showing which data you are looking at, so "the code is ready" and "we have demonstrated it live" are two separate milestones | sprintsight/web/crosstool_service.py `_crosstool_live_enabled` + docs/connectors/live-run.md + session-19 /crosstool web live demo | flagged 2026-06-26
- The real embedder, and why "change the model = re-ingest" | we swapped the fake search-vector maker (HashingEmbedder, matches only identical words) for a real meaning-based model (gte-large), behind the same offline-by-default switch as the DB/LLM/connectors; the subtle part = stored vectors and a search only compare if the SAME model made both, so we folded the model's identity into the "have I seen this before" key, which makes re-ingesting after a switch automatically re-embed instead of silently skipping (the bug the review caught) | sprintsight/ingest/embedding.py LocalEmbedder/make_embedder + embedder_signature + pipeline._content_hash + real-embedder slice | flagged 2026-06-27

## Where we are
REAL-WIRING ARC, SLICE 1 (persistent Supabase) DONE + MERGED to main (@ e10f4c4) + LIVE-VERIFIED (session 19, 2026-06-26). David chose to start "hardening for real use" on SYNTHETIC data (not real customer data), and the first slice makes the app persist to a real always-on database instead of CI's throwaway one. Built subagent-driven, eval-first, off the existing (already-CI-tested) Postgres code path. What shipped: (1) `sprintsight/config.py` `load_env(path=".env")` — a fail-safe stdlib `.env` loader (no python-dotenv): no-op when the file is absent, NEVER overrides a variable already in `os.environ` (so CI and real `export`s win), never prints values; wired as the FIRST line of `create_app()` (before `session_secret()`) and the top of `scripts/ingest.py` + `scripts/retrieve_smoke.py`. (2) `scripts/migrate.py` — a psycopg migration runner (lazy import; applies `db/migrations/*.sql` in order via one multi-statement `execute()` per file; rc 0 success / 2 no-DATABASE_URL / 3 missing `[db]` extra / 4 clean psycopg.Error, never a raw traceback). (3) `docs/db/supabase-setup.md` — the provisioning + load runbook. Spec/plan: docs/superpowers/{specs,plans}/2026-06-26-persistent-supabase*. Final opus whole-branch review = Ready to merge (0 Critical; one Important fixed = migrate graceful errors). Suite 261 passed + 3 skipped, ruff clean, watermelon 4/4 + report 4/4 + cross-tool 7/7 unchanged; CI `db` job untouched (still the persistence-logic proof). LIVE-VERIFIED against a real Supabase project (region eu-west-1): `migrate.py` applied the schema, `ingest.py` wrote 37 artifacts / 80 chunks, `retrieve_smoke.py` (a fresh process) read a cited chunk back (exit 0, top `#atlas-team/p1747900800`), re-ingest was idempotent (0 ingested / 37 skipped), direct counts artifact=37 chunk=80 embedded=80. KEY LIVE GOTCHA: Supabase's DIRECT connection (`db.<ref>.supabase.co:5432`) is IPv6-only on the free tier, so WSL2 returns "Network is unreachable"; use the SESSION POOLER string instead (`aws-0-<region>.pooler.supabase.com:5432`, username `postgres.<ref>`), which is IPv4. The real `DATABASE_URL` (with DB password) now lives in the gitignored `.env`. NOTE (from the final review): because `create_app()` now loads `.env`, a local `.env` can flip env-gated behaviour that previously needed a shell `export` (the LLM writer `SPRINTSIGHT_LLM`+`ANTHROPIC_API_KEY`, the `/crosstool` live gate, and auth dev mode `SPRINTSIGHT_ENV`); every gate stays fail-safe (defaults off, live gates still need real tokens) and the web data source is unchanged. OUT OF SCOPE (clean follow-on slices, in order): real embedder (D1) replacing HashingEmbedder; real Supabase Auth + login CSRF; populate `team_id`; switch the web screens to read artifacts FROM the DB (Approach B). The connector arc is also complete (below).

### Prior: Stage 7 Composio SDK port slice
Stage 7 (UX Polish + Connectors, Epic SS-5), COMPOSIO SDK PORT SLICE (the sixth) DONE + MERGED to main. The live Jira connector now targets the current Composio SDK. Discovery that triggered it: when `pip install '.[connectors]'` first installed the connector libraries, `from composio import ComposioToolSet` raised ImportError because `composio==0.16` is a rewrite (the class is gone; the client is now `Composio`). Fix (Approach 1, minimal faithful port): `fetch_issues` calls `Composio().tools.execute("JIRA_SEARCH_ISSUES", arguments=..., connected_account_id=os.environ["COMPOSIO_CONNECTED_ACCOUNT_ID"])`; a new pure helper `_issues_from_response(resp)` unwraps the `ToolExecutionResponse` (raises on `successful is False` so the page's fail-safe falls back to offline). The `/crosstool` gate `_crosstool_live_enabled()` now requires `COMPOSIO_CONNECTED_ACCOUNT_ID` too (six credentials), so a config gap shows plain "offline" not the misleading "offline read failed". `_to_clean`/`normalize` unchanged; `composio` pinned `>=0.16,<0.17`. Spec/plan: docs/superpowers/{specs,plans}/2026-06-26-composio-sdk-port*. LIVE STATUS: **LIVE-VERIFIED end to end (2026-06-26)** — a real human-run read of project SSSB (David's terminal, his Composio creds) returned 6 tickets, ingested + retrievable, top cited SSSB-1. Getting there flushed out three composio-0.16 quirks (all fixed + tested, merged @ a22eb0c on branch stage7-composio-live-fixes): (1) the `tools.execute` response is a plain DICT `{"data":{"issues":[...]},"error":...,"successful":...}`, not an object — `_issues_from_response` now reads dict-first; (2) `tools.execute` requires `user_id` (the owning entity) alongside `connected_account_id` or it 400s — so a THIRD env var `COMPOSIO_USER_ID` is now read, and the `/crosstool` live gate requires it (SEVEN gate vars now); (3) manual execution needs `dangerously_skip_version_check=True` (it rejects "latest"). The inner issue shape matched `_to_clean` unchanged. Editable install is required for live runs (`pip install -e '.[connectors,web]'`) or scripts/web run a stale site-packages copy. REMAINING: none for the connector arc. The full `/crosstool` WEB live demo is now DONE + LIVE-VERIFIED (session 19, 2026-06-26): set the seven gate vars (4 secret incl. GITHUB_TOKEN + the 3 Composio ids; COMPOSIO_USER_ID was a `pg...`-prefixed value confirmed live) plus `SPRINTSIGHT_ENV=dev`, launched `uvicorn sprintsight.web.app:app --port 8000`, logged in `admin@sprintsight.test`, opened `/crosstool` and saw the green `live as of 2026-06-26T07:50:02Z` badge with the two cross-tool watermelons (Atlas/SSSB-1 no-ref, Boreas/SSSB-2 PR#1 open-unmerged) and SSSB-3..6 clean, matching the CLI read. Gate-readiness was pre-checked with `python -c "from sprintsight.web.crosstool_service import _crosstool_live_enabled as g; print(g())"`. docs/connectors/live-run.md carries all three Composio env vars + the gotchas.

### Prior: Stage 7 cross-tool live-wire slice (the fifth)
Stage 7 (UX Polish + Connectors, Epic SS-5), LIVE-WIRE SLICE (the fifth) DONE + MERGED to main. The `/crosstool` page now reads the LIVE Jira board + GitHub repo behind a fail-safe gate, while staying offline-by-default and deterministic in CI. Design: `crosstool_view()` takes an injectable `source` returning `(tickets, activity, as_of, mode)`; `_active_source()` picks live connectors only when `_crosstool_live_enabled()` is true (flag `SPRINTSIGHT_CROSSTOOL_LIVE`==on AND `GITHUB_TOKEN` AND `COMPOSIO_API_KEY` AND `SPRINTSIGHT_CROSSTOOL_REPO` AND `SPRINTSIGHT_CROSSTOOL_PROJECT`), else the saved fixtures. A live read failure falls back to the offline replay with `mode="offline-failed"` and the pinned clock (never a 500, never stale-as-live). `tickets_from_artifacts` was lifted from the CLI script into `sprintsight/connect/jira_tickets.py` so web + CLI share it. A small badge surfaces the mode (live / offline replay / offline read failed). Built fully subagent-driven (3 tasks, per-task sonnet review, opus whole-branch review = Ready to merge, no Critical/Important). Full suite 240 passed + 3 skipped, ruff clean; eval gates unchanged (watermelon 4/4, report 4/4, cross-tool 7/7). Spec/plan: docs/superpowers/{specs,plans}/2026-06-26-crosstool-live-wire*. STILL DEFERRED: app-side live SDK fetch paths still need real secrets to run live end-to-end (the gate + connectors are wired, the demo needs a GITHUB_TOKEN + Composio key in the web env); per-team rollup; real Supabase/auth/CSRF.

Prior: FOURTH SLICE (cross-tool web UI) BUILT on branch `stage7-crosstool-web-ui`. New `/crosstool` page surfaces cross-tool watermelons (red) and amber stalled signals in the web UI. Reads offline replay fixtures only (`data/captured/crosstool_web_jira.json` + `crosstool_web_github.json`), no live credentials, no network in a web request. New `sprintsight/web/crosstool_service.py` data layer keeps the two data worlds (burndown vs. cross-tool) cleanly separated. All three verdict colours (red/amber/green) are visible on screen using the web-demo fixture pair. Full suite 227 passed + 3 skipped, ruff clean. The existing `/` portfolio, watermelon eval (4/4), report eval (4/4), and cross-tool eval (7/7) are all untouched.

Prior: THIRD SLICE (Goal B, cross-tool watermelon) BUILT + LIVE-VERIFIED on branch `stage7-cross-tool-watermelon` (NOT yet merged; awaiting David's review). New read-only GitHub connector (`sprintsight/connect/github.py`: pure key indexer + recorded twin + walled live fetch) plus a pure reconciler (`sprintsight/crosstool.py`) that flags the per-ticket "status versus activity" watermelon: Jira says In Progress/Done, GitHub shows no linked work or a Done-but-unmerged PR. Reuses the existing `Verdict`; the burndown `detector.py` and existing CI gates are untouched. Eval-first: new 5-case cross-tool eval (`docs/evals/cross-tool-watermelon-eval.md`, `sprintsight/evals/crosstool_eval.py`) went RED with a null reconciler, then GREEN 5/5. Full suite 207 passed + 3 skipped, ruff clean. LIVE-VERIFIED 2026-06-25: seeded a real public repo **davidmjackson/sprintsight-sandbox** (branches/PRs referencing real SSSB keys) and transitioned SSSB-1 -> In Progress, SSSB-2/3 -> Done on the live SSSB board via Composio; the demo flagged exactly 2 cross-tool watermelons citing BOTH tools (SSSB-1 no-ref, SSSB-2 PR#1 open-unmerged), leaving SSSB-3 (Done + merged PR) clean. Real-shape gotcha: GitHub's PR *list* reports merged=false even for merged PRs, so `fetch_github` derives merged from `merged_at`. Captures: data/captured/{github_sandbox_live.json, jira_SSSB_live.json}. Independent review found no blockers. Spec/plan: docs/superpowers/{specs,plans}/2026-06-25-cross-tool-watermelon*. **MERGED to main @ 7c3ab55** (local --no-ff + pushed; branch deleted). Both slices now logged + closed on the SS board (**SS-39** Jira connector, **SS-38** cross-tool, under Epic SS-5). App-side live SDK fetch declared via the `connectors` pyproject extra + documented in **docs/connectors/live-run.md** (only needs the user's GITHUB_TOKEN / Composio key to run live). Prior slice (Goal A, Jira connector) merged @ d5945dc.

**STALLED-SIGNAL SLICE (amber) BUILT OFFLINE** on branch `stage7-stalled-signal` (not yet merged). Adds a third verdict colour, amber/stalled, for an In Progress/In Review ticket whose open PR has been quiet >= 7 days (configurable `stale_after_days`), measured against an injected `as_of` so `reconcile` stays pure. Amber is a warning, NOT a watermelon (`is_watermelon` stays red-only); surfaced in a separate "stalled" list. New `PR.updated_at` field carried through the GitHub connector; cross-tool eval 5/5 -> 7/7; full suite 214 passed + 3 skipped, ruff clean. NOT live-demoable on a fresh repo (PRs are minutes old; the eval is the proof). Spec/plan: docs/superpowers/{specs,plans}/2026-06-25-stalled-signal*. NEXT: review + merge this slice; then the remaining feature slice (surface cross-tool watermelons + stalled in the web UI) needs its own brainstorm + eval-first.

Key facts for this slice:
- New module `sprintsight/connect/` with three split pieces: `fetch_issues()` (the ONLY network call; lazily imports the Composio SDK; hides Jira's custom-field mess behind a stable simplified issue dict), `normalize(issue) -> Artifact` (a PURE translator, the hard-tested unit), and `JiraConnector.fetch() -> dict[str, Artifact]` implementing a `Connector` protocol seam. Offline twin `RecordedConnector` reads `tests/fixtures/jira_sample.json`. Downstream ingest + retrieval are reused UNCHANGED.
- The A1 proof is `scripts/run_connector_demo.py`: fetch -> ingest -> retrieve -> print real tickets as cited evidence. Runs offline against the recorded sample by default; `--project <KEY>` runs it live. NO web UI changes (live Jira data does not appear in the portfolio/watermelon screens, which stay ground-truth-driven).
- `scripts/seed_demo_board.py` builds a sandbox board's worth of tickets from our ground truth: `build_issue_specs()` is pure and tested; `main()` is the GATED Jira-create loop, human-run via the Composio MCP on a clean-network day. Atlas (watermelon) carries the hidden "Draco's auth API isn't ready" dependency in a comment so the live board is gradeable.
- Eval-first held: the recorded-fixture tests pin `normalize`, the seam, the unchanged-pipeline integration, the seed builder, and the demo (12 new tests). Full suite 192 passed + 3 skipped, ruff clean. Deterministic watermelon (4/4) + report (4/4) eval gates unchanged and still the only CI gate. Live Composio/Jira paths are never exercised in CI.
- Security: connector is READ-ONLY. New secret flagged = a Composio API key for the running app (no new Jira token; reuses the connected account). Sandbox project is separate from the SS build board.
- LIVE RESULT (2026-06-24): board SSSB seeded with SSSB-1..6 (Atlas x3 incl. the Draco dependency in SSSB-1's description; Boreas x3), all `sprintsight-demo-data` + `team:<name>` labelled. Real Composio shape confirmed: issues are FLAT (no `fields` nesting), `description` is a plain string (Composio flattens ADF), `status`/`reporter` are dicts, kanban board has no sprint. `_to_clean` was rewritten to match and pinned by `test_to_clean_maps_real_composio_shape`. The two earlier review live-field worries are resolved with real evidence. Captured sample: data/captured/jira_SSSB_live.json; replay with `run_connector_demo.py --recorded data/captured/jira_SSSB_live.json`.
- STILL DEFERRED (app-runtime, not needed for the proof): the app's own Composio Python SDK fetch path (`fetch_issues`) is unrun — today's live proof went through the agent's Composio MCP + a captured replay, not the app SDK. Wiring the SDK (install `composio`, app-side Composio API key) stays a later step. David also provided a Composio connection id `ac_...` + entity name `sprintsight-sandbox`; NOT committed to git (kept for that SDK wiring). Spec: docs/superpowers/specs/2026-06-24-jira-connector-design.md; plan: docs/superpowers/plans/2026-06-24-jira-connector.md.
- OUT OF SCOPE (deferred): web UI surfacing of live data; Goal B (second connector + live cross-tool watermelon); multi-tenant team_id; persistent Supabase.

### Prior: Stage 7 first slice (UX polish)
Stage 7 (UX Polish + Connectors, Epic SS-5), FIRST SLICE done on branch `stage7-ux-polish`. A demo-ready visual identity ("Direction A", a clean Calm-SaaS look) across all five web screens. The work is almost entirely presentation: one rebuilt `static/app.css` (now a small design system of color/spacing/type tokens plus component styles), a branded top-bar shell in `base.html`, a portfolio summary band, a watermelon verdict banner with audience tabs and cited evidence/source cards on the team drill-in, and a light consistency pass on login + admin. No new pages, no JavaScript, no build step.

Key facts for this slice:
- The one new served-data behaviour (eval-first) is `summarize(rows) -> PortfolioSummary` in `service.py`: a pure fold over the portfolio rows giving headline counts (teams_tracked, watermelons, insufficient, sprint), wired into the `/` route and shown in the summary band. Verified ground truth: 5 teams, 1 watermelon (Atlas), 1 insufficient (Echo), sprint 15. Because it folds the same rows the table renders, the band cannot disagree with the table.
- No change to report-writer logic, watermelon logic, auth, the LLM gate, or the report cache. No new external calls, no new persisted data. Jinja2 autoescaping stays on for all newly rendered strings.
- Eval-first held: 9 new tests (3 summary-count contract/isolation tests + 6 structure-level HTML smoke tests for the band, shell, verdict banner, tabs, login/admin shells). Full suite 183 passed + 3 skipped, ruff clean. Deterministic watermelon (4/4) + report (4/4) eval gates unchanged and still the only CI gate.
- Built via SDD (5 implementer+reviewer task pairs on haiku/sonnet, plus an opus whole-branch review = ready to merge, two Minor fixes applied: neutral KPI styling at zero watermelons, dropped two unused CSS tokens). Spec: docs/superpowers/specs/2026-06-22-stage7-ux-polish-design.md; plan: docs/superpowers/plans/2026-06-22-stage7-ux-polish.md.
- OUT OF SCOPE (deferred): the second Stage 7 slice = real MCP connectors (live delivery-tool data instead of synthetic); mobile/responsive depth; live browser verification (presentation only, not CI).

### Prior: Stage 6 third slice
Stage 6 (Embedded status-report view, Epic SS-6), THIRD SLICE on branch `stage6-web-llm-writer`. The web drill-in can now serve real AI-written reports, switched on by a two-part gate (env flag `SPRINTSIGHT_WEB_LLM=on` AND a real `ANTHROPIC_API_KEY`). Default stays offline: `compose` (deterministic) is selected when either gate condition is absent. An in-memory cache keyed on `(team, audience)` is layered in `service.py` so repeated page loads for the same team and audience do not re-invoke the LLM within a process lifetime. Routes, templates, and the `TeamDetail` contract are unchanged; this slice is a pure service-layer change.

Key facts for this slice:
- Writer selection: `_active_writer()` in `sprintsight/web/service.py` checks `_llm_enabled()` at call time (not at import); returns `make_llm_writer()` when the gate is open, `compose` otherwise. The LLM writer is the same hybrid writer from Stage 2 arc 2 (grounded facts owned by the deterministic core; LLM authors prose only).
- Cache: `_report_cache: dict[tuple[str, str], tuple]` at module level in `service.py`, storing the shaped `(sections, sources, insufficient)` tuple. The cache check lives inside `_report_for()` (called by `team_detail()`), so a repeat (team, audience) is served without re-invoking the writer. `clear_report_cache()` drops it; an autouse fixture in `tests/web/conftest.py` calls it between tests so state never leaks.
- Security: this is the first live-LLM call path from the web app. It is off by default. The key gate ensures no API calls happen unless a real key is present. ZDR applies (Anthropic API, no new persisted data). No change to the auth layer or cookie handling.
- Eval-first held: 5 gate tests (flag combos, fallback, selection) + 4 cache tests (hit, miss, per-team, per-audience isolation) written before the implementation. Full suite 174 passed + 3 skipped, ruff clean. Deterministic watermelon (4/4) + report (4/4) eval gates unchanged.
- OUT OF SCOPE (deferred): persistent/DB-backed report storage, cache invalidation across processes, live visual verification in the browser (manual, costs money, not CI).

Stage 5 (Accounts / Auth / Admin, Epic SS-8, Story SS-34) — FIRST SLICE DONE, merged to `main` (bdb0680); branch `stage5-auth-accounts` deleted. The project's first auth layer.
- Puts a login gate in front of the Stage 6 web app, offline, behind an `Authenticator` seam.
  New package `sprintsight/web/auth/`: `hashing.py` (stdlib PBKDF2 password hash/verify, zero new
  crypto deps), `users.py` (`User`, the `Authenticator` seam, the offline `SeedAuthenticator`, and a
  deferred `SupabaseAuthenticator` stub that raises), `session.py` (signed-cookie session helpers +
  the `require_api_user` dependency). Three synthetic seed users in `seed_users.yaml` (generated by
  `scripts/make_seed_users.py`, passwords stored hashed): admin@sprintsight.test / admin-watermelon
  (admin), manager@sprintsight.test / manager-watermelon (delivery_manager), viewer@sprintsight.test
  / viewer-watermelon (viewer).
- Routes: `GET/POST /login`, `GET /logout`; the four existing routes now require login (HTML routes
  303-redirect to `/login`, JSON routes return 401); new admin-only `GET /admin/accounts` lists the
  users (email + role only) and returns 403 for non-admins. All gates fail closed.
- SECURITY (hardened per David's call after an automated review): the session signing key is
  fail-safe. `session_secret()` requires env `SPRINTSIGHT_SECRET_KEY`, and only falls back to a dev
  default when `SPRINTSIGHT_ENV=dev`; otherwise it raises and the app refuses to start. Cookie
  `https_only` is env-driven (Secure in non-dev, off in dev so HTTP works locally). Login CSRF is the
  one review item DEFERRED (documented follow-up for the Supabase/real-wiring arc).
- Run it locally (dev mode): `SPRINTSIGHT_ENV=dev .venv/bin/uvicorn sprintsight.web.app:app --port 8000`.
  Tests stay offline because the new root `tests/conftest.py` sets `SPRINTSIGHT_ENV=dev` before import.
- Eval-first held (auth is enforcement logic, so the eval is a deterministic test suite written
  before each piece): tests under `tests/web/` and `tests/web/auth/` assert anonymous is blocked,
  valid/invalid login, logout, the admin 403/200 split, hashing round-trips, and no hash/salt leak;
  the Stage 6 served-data tests were updated to log in first and still pass. Full suite 151 passed /
  3 skipped, ruff clean. Deterministic watermelon (4/4) + report (4/4) eval gates unchanged.
- OUT OF SCOPE (deferred, by design): real Supabase Auth wiring, login CSRF + Origin checks, signup
  / password-reset / email flows, the viewer-vs-delivery_manager distinction (no feature needs it
  yet), multi-tenant `tenant_id`, and any write/RAID action.
- DONE: final whole-branch opus review (no Critical/Important; 3 minors fixed), merged to `main`
  (bdb0680); Jira SS-34 In Review -> Done.

Stage 6 (Embedded status-report view, Epic SS-6) — SECOND SLICE DONE on branch `stage6-embedded-report`.
- Surfaces the existing audience-tuned report writer on the team drill-in page. The drill-in now
  shows a Status report block below the verdict/evidence, with three links (Exec / Programme / Team)
  that re-render the same page via a `?audience=` query param (no JavaScript), plus a cited Sources
  list. Default audience: programme.
- Writer seam: `service.py` calls a module-level `_writer = compose` (deterministic, offline) with
  `{team, audience, artifacts}` and folds the report into `TeamDetail` (new fields `audience`,
  `report_sections`, `report_sources`, `report_insufficient`). The LLM writer stays injectable behind
  the same seam but is NOT activated in routes this slice, so web tests stay fully offline. Sections
  are ordered by the audience profile (`AudienceProfile.required_sections`), not writer dict order, so
  a future writer swap renders correctly. Both `GET /team/{id}` and `GET /api/team/{id}` gained the
  optional `?audience=` param; unknown value falls back to programme; unknown team still 404s; both
  routes stay login-gated by Stage 5 auth. HTML + JSON render from the same service output.
- Echo (thin data): the writer abstains (`insufficient_evidence`), the page shows "Not enough evidence
  to write a report." No fabrication path; section keys map to headings only via `heading_for`.
- Eval-first held: served-data tests, not pixels. `tests/web/` asserts, per audience, the served
  report's grounded facts + section set + profile order, Echo insufficient, the `?audience=` selection
  and fallback, and an HTML smoke test for the switcher/report block. Full suite 165 passed / 3 skipped,
  ruff clean. Deterministic watermelon (4/4) + report (4/4) eval gates unchanged.
- Built via SDD (3 implementer + reviewer task pairs, fresh agents each). Final opus whole-branch
  review = READY TO MERGE, no Critical/Important; a fix wave cleared the one substantive minor
  (profile-ordered sections + an order test) plus a sources guard and a redundant noqa.
- OUT OF SCOPE (deferred): live LLM prose in the browser (seam present, not switched on), rich
  markdown-to-HTML styling, persistent DB, writes/RAID, remembering the audience across pages.
- OUTSTANDING: integrate the branch (merge); Jira SS-6 board move.

Stage 6 (Portfolio + Watermelon UI, Epic SS-6) — FIRST SLICE DONE, merged via PR #1 (b9cbe66).
- The project's first web UI and first HTTP serving layer. A FastAPI app at `sprintsight/web/`:
  `service.py` (pure data layer: `portfolio()` + `team_detail()` over the existing `graph_detector()`
  path, shaping frozen view-models `TeamRow`/`TeamDetail`/`EvidenceItem`); `app.py` (`create_app()`
  + module-level `app`); Jinja2 templates + `static/app.css`. Two views: a portfolio grid (reported
  vs computed RAG + watermelon badge) and a per-team drill-in (headline, signals, evidence).
- Routes: `GET /` and `GET /team/{id}` (HTML), `GET /api/portfolio` and `GET /api/team/{id}` (JSON,
  the seam for later auth / richer frontend; 404 on unknown team). HTML + JSON render from the same
  service output so they cannot drift.
- Run it locally: `.venv/bin/uvicorn sprintsight.web.app:app --port 8000` (then `/` and `/team/atlas`).
- Eval-first held: tests under `tests/web/` assert the served data vs the Sprint-15 ground truth
  (Atlas watermelon/red, Boreas/Cygnus/Draco not, Echo insufficient-evidence) + light HTML smoke
  tests. New optional `web` extra (fastapi/jinja2/httpx/uvicorn); CI `lint-and-test` now installs
  `.[dev,eval,web]`. Offline, corpus-driven, no key/DB. Also added a backward-compatible `signals`
  field to `Verdict` (watermelon eval still 4/4). Full suite 118 passed / 3 skipped, ruff clean.
- OUT OF SCOPE for that slice (login/auth now being added in Stage 5 above): persistent DB, the
  embedded LLM status report, writes/RAID actions, and visual polish (Stage 7, SS-5). The drill-in is
  plain page navigation (no JavaScript/HTMX) in this slice.
- DONE: merged via PR #1 (b9cbe66); Jira SS-33 Done.

Stage 0 (Foundation, Epic SS-3) and Stage 1 (Ingestion + RAG Core, Epic SS-2) are BOTH COMPLETE.
Stage 2 (Status Report Agent, Epic SS-1) — BOTH ARCS DONE.
- Arc 1: the SS-1.5 report-quality eval is GREEN (4/4 cases: boreas-exec, atlas-programme,
  echo-thin, audience-triple; all dimensions pass). Echo thin-data team in the corpus (37 artifacts).
  Deterministic `compose` (behind the `ReportWriter` seam, sprintsight/report/writer.py) produces
  audience-tuned, cited reports and passes the fabrication trap. The report eval
  (`scripts/run_report_eval.py`) gates the `lint-and-test` CI job.
- Arc 2: LLM-backed report-writer (ADR-0001's report-writer node) is BUILT and merged (374bf6c).
  HYBRID design — the deterministic core (`_grounded_facts` + `_compose_sections`, refactored out
  of `compose`) owns all numbers/RAG/cited `claims`; the injected LLM completer authors only the
  section PROSE; a validator falls violating/over-cap sections back to `compose` prose. So the
  eval's grounding/citation/fabrication assertions hold BY CONSTRUCTION (LLM output can never reach
  `claims`). Code: sprintsight/report/llm_writer.py (`make_llm_writer(complete=None, model=...)`,
  default model claude-sonnet-4-6). `compose` stays the CI gate/fallback; the LLM path is offline-
  tested with a fake completer and runs live under `scripts/run_report_eval.py --llm` (key-gated,
  CI never calls the API). Verified live 2026-06-18: `--llm` eval 4/4, prose genuinely LLM-authored
  + audience-distinct, grounded. Final opus whole-branch review = Ready to merge, no Critical/Important.
  Deferred follow-ups (next arc, all latent/cosmetic): strengthen fallback tests to pin the
  mechanism; log on the writer's `except`; handle completer `max_tokens` truncation; Facts keyword-
  arg construction; direct programme/team section-key tests; optional `.env` autoload in the eval
  script. See .git/sdd/progress.md (arc-2 section) + docs/superpowers/{specs,plans}/2026-06-18-*.

Stage 1 recap (7/7): SS-19 corpus, SS-21 harness (+Langfuse), SS-18 watermelon eval, SS-20
migrations, SS-24 ingestion, SS-23 retrieval, SS-22 baseline detector. Watermelon eval GREEN
(4/4 classification, 4/4 evidence). Code: sprintsight/{evals,ingest,retrieval,detector.py},
db/migrations/, data/ corpus. CI: lint-and-test (ruff + pytest + report eval) and `db` job
(migrate + ingest + retrieve on pgvector:pg16) — both green on push.

Stage 4 (Observability + Evals, Epic SS-7): DONE on branch `stage4-observability-llm-judge`. Jira Story SS-30.
- LLM-as-judge readability scorer: `sprintsight/evals/judge.py`. Scores a finished report 1-to-5
  on four prose dimensions (clarity, audience_fit, coherence, actionability) via an injected grader.
  Pass bar: every dimension >= 3 AND mean >= 3.5. Advisory only. Does not block the build. Fake grader
  in CI; real Anthropic grader on the key-gated path. (actionability dimension recalibrated in the
  writer-readability arc below; see that section.)
- Calibration meta-eval: `sprintsight/evals/calibration.py`. Runs the judge against hand-labelled
  good/bad anchor reports (`run_calibration`) to prove the judge separates good from bad before it
  is trusted as a gate. Both modules green in CI with fakes; live paths key-gated.
- Per-node graph tracing: `sprintsight/graph/builder.py` now emits one `graph:run` span wrapping
  each run, and one `node:<name>` span per node, via the existing optional Tracer. No-op default
  keeps CI fully offline. Design recorded in `docs/adr/ADR-0003-graph-tracing.md`.
- Opt-in `--judge` flag on `scripts/run_report_eval.py` appends an advisory readability pass
  (never changes exit code). `scripts/run_calibration.py` is the live calibration runner.
- Deferred: promoting the readability judge to a hard CI gate (pending calibration proving it
  separates good from bad); Langfuse dashboards; consuming retrieved chunks downstream in the
  graph (pre-existing deferred item from Stage 3).

Stage 4 follow-up: writer-readability arc (Epic SS-7), on branch `writer-readability-arc`, ready to merge.
- Why: the Stage 4 judge, run live on our REAL reports, scored them below the readability bar.
  This arc fixed the deterministic `compose` writer eval-first, and surfaced a real principle.
- Shipped (commits a122629, d95c2fd, e72f3cd, 216ef14): (1) a shared human-heading renderer
  `sprintsight/report/render.py` (snake_case keys stay the contract; the judge reads through it);
  (2) multi-item RAID sections render as a list, not a run-together blob; (3) an exec-directed,
  non-circular, grounded "ask"; (4) the judge's `actionability` dimension recalibrated so a grounded
  recommendation is sufficient and the absence of an invented owner/date/decision is NOT penalised.
- The principle (LEARNING-LOG Entry 6): the judge demanded owners/dates/decisions, which our
  no-fabrication rule forbids inventing. We corrected the rubric (move 3), not the facts (forbidden)
  and not the bar (gaming). Guarded by the calibration meta-eval: still 4/4 live after the change
  (good-exec 5/5/5/5; vague-ask bad anchor still actionability 1). audience_fit was NOT touched.
- Live judge result: compose boreas-exec 3.0 / atlas-programme 2.2 (clean+grounded but terse; the
  deterministic ceiling, blocked on audience_fit = business-impact narrative). LLM writer under the
  recalibrated judge: boreas-exec 4.2 PASS, atlas-programme 3.0 (one dim off). Deterministic gate
  unchanged + green (watermelon 4/4, report 4/4, 80 passed/3 skipped, ruff clean).
- FOLLOW-ON ARC DONE (LLM writer readability, branch `llm-writer-readability-arc`): the LLM writer
  now clears the advisory judge on BOTH audiences, measured as the median of 3 live samples:
  boreas-exec 5.00 PASS (5/5/5/5), atlas-programme 4.00 PASS (5/4/3/4). Shipped: (1) writer prompt
  directives + a worked exemplar (lead with the one to watch, grounded watch-points, no passive
  reassurance, register); (2) `sample_judge` 3-sample median in judge.py so the noisy judge is
  measurable; (3) the advisory `--judge` pass now prints median + noise range. KEY FIX found during
  live measurement: the mechanics filter matched "points" as a SUBSTRING, so the LLM's own
  "watch-points" prose was rejected and exec fell back to terse compose (stuck at 2.75). Replaced
  with a shared boundary-aware `contains_mechanics()` (audience.py, used by writer + eval); allows
  "watch-points"/"touchpoints" but still catches "38 points"/"story points"/"velocity". Deterministic
  gate stayed green throughout (89 passed/3 skipped, ruff clean, watermelon 4/4, report 4/4).
  Judge stays ADVISORY (not promoted to a gate). compose stays the CI gate + offline fallback.
  Docs: docs/superpowers/{specs,plans}/2026-06-19-llm-writer-readability*.
- WATCH (for any future judge gate promotion): atlas-programme `coherence` median sits at 3 (the
  per-dimension floor), so a noisy run could dip it below bar. Promotion still deferred.

Stage 4 follow-up: judge-gate arc (Epic SS-7), on branch `judge-gate-arc`, MERGED to main (live-verified).
- What: the LLM-judge readability pass can now FAIL a deliberate, key-holding pre-merge run via a new
  `--judge-gate` flag on `scripts/run_report_eval.py`. This is the live-only gate David chose ("Option
  A"); CI is untouched and stays offline (the deterministic report eval is still the only CI gate).
- Design: `judge_gate_decision(medians, calibration_ok) -> GateDecision` (pure, in judge.py) owns the
  block/allow rules. Two safety catches: (1) the gate runs the calibration meta-eval first and only
  blocks if the judge is trusted that run; (2) it scores each report as a 5-sample median (advisory
  `--judge` stays 3). Fails SAFE everywhere: missing key returns 2, an infra exception or a
  calibration miss yields not-blocking, and an unscored (insufficient-evidence) report never blocks.
  Shared `_score_one` helper de-dupes the per-case median for advisory + gate. Exit code is non-zero
  iff the deterministic eval fails OR the gate blocks.
- Built eval-first via SDD (3 implementer+reviewer tasks, opus whole-branch review = ready to merge,
  no Critical/Important). Suite 101 passed/3 skipped, ruff clean. Spec/plan:
  docs/superpowers/{specs,plans}/2026-06-21-judge-gate*. Ledger .superpowers/sdd/progress.md.
- LIVE VERIFIED 2026-06-21 (`--llm --judge-gate`, real key): deterministic 4/4; calibration_ok=True;
  GATE OK with boreas-exec mean 4.50 PASS and atlas-programme mean 4.50 PASS (echo-thin n/a, not
  blocking); exit 0. The blocking path (below-bar -> blocks) is proven by the offline tests; the live
  run proves the happy path, the live calibration trust gate, and the exit-code wiring.
- Judge stays ADVISORY in CI (not promoted to a CI gate). `--judge-gate` is operator-run only.

Stage 3 (LangGraph, Epic SS-4) — DONE. Jira Story SS-29.
- Three-node LangGraph graph built in `sprintsight/graph/`: `GraphState` dataclass; node functions
  `retrieval_node`, `risk_node`, `report_writer_node` (each `state -> dict`); `build_graph()`
  constructs the linear `StateGraph`; `run(inputs, writer, retriever, k)` executes it end-to-end.
- Graph-level adapters: `graph_detector(team_id, artifacts)` wraps the graph for the watermelon eval;
  `graph_writer(team_id, artifacts, audience)` wraps it for the report eval. Both eval scripts
  (`scripts/run_watermelon_eval.py`, `scripts/run_report_eval.py`) re-pointed through the graph.
- Both evals GREEN through the graph: watermelon 4/4 classification + 4/4 evidence; report-quality
  4/4 (all dimensions). Both gate CI (unchanged).
- Retrieval node: calls `InMemoryRetriever` + `HashingEmbedder` CI-safe; chunks land in
  `state["retrieved"]`; NOT yet consumed by risk or report-writer nodes (deferred — next arc).
- `langgraph` added to `pyproject.toml` as a core dependency.
- `detector.py`, `report/`, `retrieval/` — UNMODIFIED. Default path import-clean of `anthropic`.
- Deferred follow-ups (not blocking): consume retrieved chunks downstream; node promotion per ADR-0001
  triggers (evals must justify); swap InMemoryRetriever for PostgresRetriever in-graph.

Next in Stage 2 (optional, eval-first, superseded by Stage 3): extend eval cases the LLM now
warrants — LLM-as-judge readability/tone, stricter audience differentiation, RAID cite-through.

Anthropic API key: a real sk-ant key is now wired in .env (len 108). NOTE the project has NO
.env auto-loader (no load_dotenv) — live `--llm` runs must export ANTHROPIC_API_KEY into the env
(a minimal loader already exists at scripts/verify_langfuse.py if we want to share it).

Still-open real-wiring items (not blocking, all flagged on tickets): provision a persistent Supabase
Postgres+pgvector (only CI's ephemeral DB used so far); finalise the in-region 1024-dim embedding
model (D1) to replace HashingEmbedder; populate artifact.team_id for DB-side team scoping; add a
.env loader for non-CI runs. These become load-bearing when the system runs outside CI.

## Tracking setup (done)
- Jira project: key SS, name SprintSight, team-managed (next-gen).
- Issue model: Epic (container) + Story (work). Story to Epic via the Parent field.
- Statuses: Backlog, To Do, In Progress, In Review, Done. Blocked is a flag, not a status.
- Tooling: Composio MCP connected to Claude Code (managed Connect, OAuth, HTTP transport).
  Claude Code creates and transitions issues. Composio routes via its servers (flagged as a
  gov/security swap point; for the showcase on synthetic data it is fine).
- Workflow rules: docs/jira/workflow.md (transition rules, WIP limit 1 to 2, eval gate, DoD).

## Epic key map
Foundation & De-risking = SS-3 (holds all 9 Stage-0 Stories). Other 7 Epics are empty by design.
Full map: docs/jira/epic-key-map.md (generate/refresh from Jira if missing).

## Foundation Stories
- SS-1.1 Set up Jira tracking — DONE.
- SS-1.2 (SS-11) Repo, CLAUDE.md, HANDOVER.md, secrets, CI — DONE. Repo committed on `main` (initial commit 983324a) and pushed to github.com/davidmjackson/sight. .gitignore (real .env + .venv + caches ignored, .env.example tracked — verified); pyproject.toml (ruff + pytest config); .github/workflows/ci.yml (checkout -> setup-python 3.11 -> pip install .[dev] -> ruff check -> pytest); tests/test_smoke.py placeholder. CI ran GREEN on push (Actions run 27703300519, lint-and-test passed). Minor follow-up (non-blocking): bump checkout/setup-python action versions when convenient (Node 20 deprecation warning).
- SS-1.3 Data strategy — LOCKED; board: DONE. docs/data/data-strategy.md.
- SS-1.4 Watermelon eval spec — LOCKED (deterministic grading); board: DONE. docs/evals/watermelon-eval.md.
- SS-1.5 Report-quality eval spec — LOCKED (audience profiles confirmed); board: DONE. docs/evals/report-quality-eval.md.
- SS-1.6 ADR: cut agent graph to three nodes — DONE (board + spec, 2026-06-17). docs/adr/ADR-0001-three-agent-graph.md.
- SS-1.7 Moat spec — DONE (board + spec; three behaviours confirmed 2026-06-17). docs/moat/moat-behaviours.md.
- SS-1.8 Lock auth + hosting residency — DONE (board + spec). Locked: managed Supabase UK/EU, gov self-host as future swap. docs/adr/ADR-0002-auth-and-residency.md.
- SS-1.9 Base schema design — DONE (board + spec; decisions D1-D5 locked 2026-06-17). docs/schema/schema-design.md. Seven groups + full DDL: identity/access (on Supabase Auth), delivery domain, source corpus, RAID vs risk-findings, signals, outputs, unified audit/reasoning log. Watermelon flag derived (v_watermelon view), not stored. RAID recommend-only (risk_finding -> raid_entry on human accept; evidence via join table). Vector dimension locked at 1024. SIGNED OFF (security review 2026-06-17); SS-1.8 lock confirms encryption-at-rest.

## Key decisions (locked)
- Showcase-first; single-tenant; persist on anonymized/synthetic data; ZDR on Anthropic API.
- Backend Python/FastAPI. LangGraph for orchestration (Stage 3+), not full LangChain. Langfuse for evals/tracing.
- Agent graph cut to THREE nodes for the showcase: retrieval, risk/reconciliation, report-writer.
  Planner, analysis, critic stay as functions/prompts until evals justify promotion. (ADR-0001.)
- Data: scenario-first synthetic. Four teams, two sprints. Atlas (watermelon), Boreas (true green),
  Cygnus (honest amber), Draco (tricky near-miss). Atlas depends on Draco's auth API.
- Evals: deterministic-first. LLM-as-judge deferred to Stage 4. Evidence required, not just label.
- Moat: three methodology-aware behaviours (cross-team dependency slip; flat burndown vs reported
  on-track; risk in chat missing from RAID). Seeded into Atlas/Draco.
- Auth + hosting: managed Supabase UK/EU (Postgres + pgvector + Auth + storage, encryption-at-rest);
  gov self-host as future swap. (ADR-0002.)

## Stage-0 decisions (all resolved 2026-06-17)
1. SS-1.7 moat — RESOLVED 2026-06-17. All three behaviours confirmed and folded into
   moat-behaviours.md (now LOCKED): B1 cross-team slip in scope (guardrail: discoverable
   dependencies only, no inferred links); B2 computed signals + transparent reference
   thresholds (burn ratio <~0.4 over 2 sprints, velocity decline ≥~25-30%, carry-over ~doubling;
   tunable, not hard gates); B3 RAID recommend-only as a permanent principle. Remaining: move
   SS-1.7 board status In Progress → Done.
2. SS-1.8 auth + residency: RESOLVED. Locked to managed Supabase UK/EU; gov self-host as future swap.
   Recorded in ADR-0002. Remaining: board move.
3. SS-1.9 schema: RESOLVED 2026-06-17. All 5 decisions locked to the recommendations and the spec is
   written (docs/schema/schema-design.md). D1 self-hostable in-region embedding model, vector
   dimension fixed at 1024 (exact model finalised at Stage 1 under eval). D2 tenant_id column
   everywhere, no RLS yet. D3 event.detail = references + short rationale, no raw bodies. D4 role
   enum (admin/delivery_manager/viewer). D5 chunk-level citations. Security review signed off
   2026-06-17; encryption-at-rest confirmed via the SS-1.8 lock. Remaining: board move.

## Docs map
- docs/jira/workflow.md — board rules for Claude Code.
- docs/jira/sprintsight-build-items.json — the 17 issues as created.
- docs/jira/epic-key-map.md — Epic to key map.
- docs/data/data-strategy.md — SS-1.3.
- docs/evals/watermelon-eval.md — SS-1.4.
- docs/evals/report-quality-eval.md — SS-1.5.
- docs/moat/moat-behaviours.md — SS-1.7.
- docs/schema/schema-design.md — SS-1.9 (SIGNED OFF; decisions locked).
- docs/adr/ADR-0001-three-agent-graph.md — SS-1.6 (three-node cut).
- docs/adr/ADR-0002-auth-and-residency.md — SS-1.8 (managed Supabase UK/EU).
- docs/adr/ADR-0003-graph-tracing.md — SS-30 (per-node graph tracing, optional Tracer).
- sprintsight-braindump.md — project context (in Project knowledge).

## Stage 1 build log (Epic SS-2 — all DONE)
Eval-first order held throughout; full story map in docs/jira/stage-1-stories.md.
1. SS-2.1 (SS-19) synthetic corpus + ground-truth labels — 36 artifacts under data/corpus/, hand-authored truth at data/ground-truth/labels.yaml.
2. SS-2.2 (SS-21) eval harness — sprintsight/evals/ (Case/Assertion/SuiteReport/run_suite + fixtures loader + Langfuse v4, provisioned Cloud EU).
3. SS-2.3 (SS-18) watermelon eval (SS-1.4) — sprintsight/evals/watermelon.py; 4 cases, dual gates; landed RED by design (null_detector).
4. SS-2.4 (SS-20) migrations — db/migrations/0001_init.sql (schema Groups 2/3/5, pgvector, vector(1024)); applied on pgvector:pg16 in CI.
5. SS-2.5 (SS-24) ingestion — sprintsight/ingest/ (chunker + Store [InMemory/Postgres] + Embedder [HashingEmbedder stand-in, D1 TODO]); idempotent on content_hash.
6. SS-2.6 (SS-23) retrieval — sprintsight/retrieval/ (InMemoryRetriever + PostgresRetriever pgvector <=>).
7. SS-2.7 (SS-22) baseline detector — sprintsight/detector.py; deterministic, recommend-only; turned the watermelon eval GREEN (4/4 + 4/4). scripts/run_watermelon_eval.py exits 0.

## Next actions (Stage 2, Epic SS-1 — Status Report Agent, first arc complete)
Report-quality eval arc is DONE (eval GREEN, gates CI). Next arc: LLM report-writer.
1. Wire the Anthropic API key (.env) — needed for the real report-writer LLM calls.
2. Build the LLM-backed report-writer (the report-writer node per ADR-0001) behind the
   `ReportWriter` seam; keep the deterministic `compose` as fallback / test fixture.
3. Extend eval cases as Stage 2 Stories warrant (audience-tuning, grounding gates, RAID
   cite-through, cross-team dependency signal).

## Open real-wiring items (not blocking the build; all flagged on tickets)
- DONE (slice 1, session 19): persistent Supabase Postgres+pgvector, app persists the synthetic corpus, survives restart.
- DONE (slice 2, session 21): the in-region 1024-dim embedding model (D1) — `LocalEmbedder`/`gte-large` behind `SPRINTSIGHT_EMBEDDER=local`, eval-proven semantic retrieval. Operator step remaining: re-embed the live Supabase via docs/embedder/real-embedder.md.
- NEXT (slice 3): populate artifact.team_id (+ load delivery-domain rows: team/sprint/metrics/burndown) for DB-side team scoping and a DB-backed detector.
- NEXT (slice 4): switch the web screens to read artifacts FROM the DB (Approach B).
- NEXT (slice 5): real Supabase Auth + login CSRF + per-tenant RLS policies (needs team_id).
- Stage 2+ report-writer LLM calls need the Anthropic API key wired (.env) — now loaded by the .env loader.

## Eval-first guardrail (still governs)
No feature code before the eval it must pass exists. SS-1.5 report eval is now GREEN and gating CI.
The LLM report-writer is next; any new Stage-2 behaviour requires an eval case first.
Out of Stage-2 scope by decision: portfolio/watermelon UI is Stage 6 (SS-6). Optional housekeeping:
bump CI action versions (Node 20 deprecation warning).
