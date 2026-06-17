# Sprintsight — HANDOVER

Living cross-session handover. Read this first when starting a new thread or agent.
Last updated: 2026-06-17 (Claude Code session: STAGE 0 CLOSED, 9/9 Foundation Stories Done. Repo initialised on `main`, pushed to github.com/davidmjackson/sight, CI green on push (Actions run 27703300519); SS-1.6/1.8/1.9 walked Backlog -> Done and SS-1.2/SS-11 In Progress -> Done, all with AC-check comments; SS-1.7 was already Done). System of record: Jira (statuses) + the docs below (specs/decisions).

## Who reads what
- This file (HANDOVER.md): shared current state. BOTH the planning thread and Claude Code read it. One state file on purpose; do not fork it.
- Claude Code (building): also read CLAUDE.md for build conventions and how to drive the Jira board.
- Planning thread (Claude Desktop/web): operating manual is the Project instructions + sprintsight-braindump.md.
- docs/ specs are shared by both. Principles live in the brain dump, state lives here, build conventions live in CLAUDE.md. Each fact has one home.

## Where we are
Stage 0 (Foundation, Epic SS-3) is COMPLETE: 9 of 9 Stories Done. Every Stage-0 spec and decision is
written, locked, and reflected on the board (data strategy, both eval specs, moat spec, base schema,
both ADRs), and the repo plumbing (SS-1.2) is live: code is committed on `main`, pushed to
github.com/davidmjackson/sight, and GitHub Actions CI (ruff + pytest) ran GREEN on push. The other 7
Epics are empty by design. Next up is Stage 1 (ingestion + RAG core), which opens now that the
Stage gate is cleared. Eval-first still governs: no feature code before the eval it must pass exists.

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

## Do NOT do yet
- Do not generate the data corpus or write the eval harness. That is early Stage 1.
- Keep all specs as paper specs until Stage 0 closes.
- Eval-first: no feature code before the eval it must pass exists.

## First actions in the new thread
Stage 0 is closed (9/9 Done) and the repo is live on GitHub with green CI. Stage 1 (Ingestion + RAG
Core, Epic SS-2) is open and its 7 Stories are CREATED in Backlog (full map + eval-first order:
docs/jira/stage-1-stories.md). Build order, eval-first:
1. SS-2.1 (SS-19) synthetic corpus + ground-truth labels — DONE (committed 776e719). 36 artifacts under data/corpus/, hand-authored truth at data/ground-truth/labels.yaml, conventions in data/README.md. Verified: ids match manifest, no orphans, expected_evidence resolves, numbers consistent, cross-team thread reconcilable + the RAID gap confirmed. The fixtures every other Stage-1 Story consumes.
2. SS-2.2 (SS-21) eval harness + SS-2.4 (SS-20) migrations — DONE (committed 9df8664; CI run 27704946566 green: lint-and-test + a new `migrations` job applying 0001_init.sql on pgvector/pgvector:pg16). Harness at sprintsight/evals/ (Case/Assertion/SuiteReport/run_suite + fixtures loader + optional Langfuse). Migration db/migrations/0001_init.sql = schema Groups 2/3/5. RESIDUAL on SS-21: live Langfuse trace capture is wired but unverified until LANGFUSE_PUBLIC_KEY/SECRET_KEY exist (needs a provisioned Langfuse project) — flagged on the ticket, not silently closed.
3. NEXT: SS-2.3 (SS-18) watermelon eval (SS-1.4) — build the 4 cases on the harness using the corpus fixtures; it should land RED (no detector yet). Then SS-2.5 (SS-24) ingestion -> SS-2.6 (SS-23) retrieval; then SS-2.7 (SS-22) detector turns the eval GREEN. Stage-1: 3 of 7 done (SS-19, SS-20, SS-21).
Out of Stage-1 scope by decision: SS-1.5 report eval opens Stage 2 (Epic SS-1); portfolio/watermelon UI is Stage 6 (SS-6). Optional housekeeping: bump CI action versions (Node 20 deprecation warning).
