# Sprintsight — HANDOVER

Living cross-session handover. Read this first when starting a new thread or agent.
Last updated: 2026-06-21 (Claude Code session: STAGE 6 first slice (Portfolio + Watermelon UI, Epic SS-6) complete on branch `stage6-watermelon-ui` — see "Where we are" below. Prior: STAGE 4 (Observability + Evals, Epic SS-7, Story SS-30) complete on branch `stage4-observability-llm-judge`. LLM-as-judge readability scorer added (`sprintsight/evals/judge.py`): four prose dimensions (clarity, audience_fit, coherence, actionability), injected grader (fake in CI, real Anthropic on the key-gated path), advisory pass bar (every dim >= 3, mean >= 4, non-gating). Calibration meta-eval added (`sprintsight/evals/calibration.py`): grades the judge against hand-labelled good/bad anchor reports before it becomes a gate. Per-node graph tracing added to `sprintsight/graph/builder.py` via optional Tracer (no-op default, CI stays offline; one `graph:run` span wraps the run, each node emits a `node:<name>` span). ADR-0003 records the tracing design. Opt-in `--judge` flag on `scripts/run_report_eval.py` runs the readability pass (advisory, never changes exit code). `scripts/run_calibration.py` runs the live calibration. Both new modules green in CI with fakes; live paths key-gated. Deterministic watermelon + report evals unchanged, still the CI gate. Prior: STAGE 3 DONE (SS-29, branch stage3-langgraph-graph); STAGE 2 DONE (arc 2, 374bf6c); STAGE 0 + STAGE 1 CLOSED. Repo on github.com/davidmjackson/sight; CI green. System of record: Jira (statuses) + the docs below (specs/decisions). FOLLOW-UP THIS SESSION (2026-06-19): writer-readability arc on branch `writer-readability-arc` (see the dedicated section below).

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

## Where we are
Stage 6 (Portfolio + Watermelon UI, Epic SS-6) — FIRST SLICE DONE on branch `stage6-watermelon-ui` (not yet merged).
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
- OUT OF SCOPE (deferred, by design): login/auth (Stage 5, SS-8), persistent DB, the embedded LLM
  status report, writes/RAID actions, and visual polish (Stage 7, SS-5). The drill-in is plain page
  navigation (no JavaScript/HTMX) in this slice.
- OUTSTANDING: final whole-branch review, then integrate the branch (merge/PR); Jira SS-6 board moves.

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
- Provision a persistent Supabase Postgres+pgvector (only CI's ephemeral DB used so far).
- Finalise the in-region 1024-dim embedding model (D1) to replace HashingEmbedder; semantic retrieval recall depends on this.
- Populate artifact.team_id (+ load delivery-domain rows: team/sprint/metrics/burndown) for DB-side team scoping and a DB-backed detector.
- Stage 2+ will need the Anthropic API key wired (.env) for the actual report-writer LLM calls.

## Eval-first guardrail (still governs)
No feature code before the eval it must pass exists. SS-1.5 report eval is now GREEN and gating CI.
The LLM report-writer is next; any new Stage-2 behaviour requires an eval case first.
Out of Stage-2 scope by decision: portfolio/watermelon UI is Stage 6 (SS-6). Optional housekeeping:
bump CI action versions (Node 20 deprecation warning).
