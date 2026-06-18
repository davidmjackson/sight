# Sprintsight — HANDOVER

Living cross-session handover. Read this first when starting a new thread or agent.
Last updated: 2026-06-17 (Claude Code session: STAGE 0 + STAGE 1 BOTH CLOSED. Stage 0 = 9/9 Foundation Stories. Stage 1 (Epic SS-2, Ingestion + RAG Core) = 7/7 Stories Done: corpus, eval harness, watermelon eval, migrations, ingestion, retrieval, detector. The watermelon eval is GREEN (4/4 classification + 4/4 evidence). Repo on github.com/davidmjackson/sight; CI green incl. a `db` job that applies the migration + ingests + retrieves on pgvector:pg16. Langfuse Cloud EU provisioned. System of record: Jira (statuses) + the docs below (specs/decisions).

## Who reads what
- This file (HANDOVER.md): shared current state. BOTH the planning thread and Claude Code read it. One state file on purpose; do not fork it.
- Claude Code (building): also read CLAUDE.md for build conventions and how to drive the Jira board.
- Planning thread (Claude Desktop/web): operating manual is the Project instructions + sprintsight-braindump.md.
- docs/ specs are shared by both. Principles live in the brain dump, state lives here, build conventions live in CLAUDE.md. Each fact has one home.

## Where we are
Stage 0 (Foundation, Epic SS-3) and Stage 1 (Ingestion + RAG Core, Epic SS-2) are BOTH COMPLETE.
Stage 2 (Status Report Agent, Epic SS-1) — first arc DONE: the SS-1.5 report-quality eval is
GREEN (4/4 cases: boreas-exec, atlas-programme, echo-thin, audience-triple; all dimensions pass).
The Echo thin-data team was added to the corpus (now 37 artifacts). A deterministic report composer
(`compose` behind the `ReportWriter` seam in sprintsight/evals/report.py) produces audience-tuned,
cited reports and passes the fabrication trap; the LLM-backed writer remains a deferred drop-in
(open-wiring). The report eval (`scripts/run_report_eval.py`) now gates the `lint-and-test` CI job.

Stage 1 recap (7/7): SS-19 corpus, SS-21 harness (+Langfuse), SS-18 watermelon eval, SS-20
migrations, SS-24 ingestion, SS-23 retrieval, SS-22 baseline detector. Watermelon eval GREEN
(4/4 classification, 4/4 evidence). Code: sprintsight/{evals,ingest,retrieval,detector.py},
db/migrations/, data/ corpus. CI: lint-and-test (ruff + pytest + report eval) and `db` job
(migrate + ingest + retrieve on pgvector:pg16) — both green on push.

Next in Stage 2: build the LLM-backed report-writer agent (the actual report-writer node per
ADR-0001) to replace the deterministic composer seam, then audience-tuning and grounding/
fabrication gates. Wire the Anthropic API key (.env) before starting the LLM report-writer.

Still-open real-wiring items (not blocking, all flagged on tickets): provision a persistent Supabase
Postgres+pgvector (only CI's ephemeral DB used so far); finalise the in-region 1024-dim embedding
model (D1) to replace HashingEmbedder; populate artifact.team_id for DB-side team scoping. These
become load-bearing when the system runs outside CI / on the real embedding model.

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
