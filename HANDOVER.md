# Sprintsight — HANDOVER

Living cross-session handover. Read this first when starting a new thread or agent.
Last updated: 2026-06-17 (Claude Code session: git repo initialised on `main`, .gitignore + CI skeleton added and verified green locally; SS-1.6/1.8/1.9 transitioned Backlog -> To Do -> In Review -> Done with AC-check comments; SS-1.7 confirmed already Done; SS-1.2 confirmed already In Progress). System of record: Jira (statuses) + the docs below (specs/decisions).

## Who reads what
- This file (HANDOVER.md): shared current state. BOTH the planning thread and Claude Code read it. One state file on purpose; do not fork it.
- Claude Code (building): also read CLAUDE.md for build conventions and how to drive the Jira board.
- Planning thread (Claude Desktop/web): operating manual is the Project instructions + sprintsight-braindump.md.
- docs/ specs are shared by both. Principles live in the brain dump, state lives here, build conventions live in CLAUDE.md. Each fact has one home.

## Where we are
Stage 0 (Foundation, Epic SS-3): 8 of 9 Stories Done. Every Stage-0 spec and decision is written,
locked, and now reflected on the board: data strategy, both eval specs, moat spec, the base schema
(SS-1.9), and both ADRs (SS-1.6 three-node cut, SS-1.8 auth + residency) are all Done. The only
Story still open is SS-1.2 (SS-11, In Progress): the local repo plumbing is done (git init on `main`,
.gitignore, pyproject.toml, CI skeleton at .github/workflows/ci.yml, placeholder smoke test — ruff +
pytest verified green locally in a throwaway .venv). What's NOT yet done, and why SS-1.2 cannot be
closed: the repo is not committed and has no remote, so the AC "CI runs lint+test on push, green on
an empty suite" is unproven until the repo is pushed to a remote (e.g. GitHub) and Actions runs.
That push is an outward-facing step awaiting the owner's go-ahead.

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
- SS-1.2 (SS-11) Repo, CLAUDE.md, HANDOVER.md, secrets, CI — IN PROGRESS (board already there). Done: docs/jira/workflow.md, root CLAUDE.md/HANDOVER.md/README.md, .env.example; git init on `main`; .gitignore (real .env + .venv + caches ignored, .env.example tracked — verified); pyproject.toml (ruff + pytest config); .github/workflows/ci.yml (checkout -> setup-python 3.11 -> pip install .[dev] -> ruff check -> pytest); tests/test_smoke.py placeholder. ruff + pytest run GREEN locally (RC 0). Outstanding before Done: (1) initial commit (everything staged, none committed); (2) create a remote (GitHub) and push so CI actually runs and the "green on push" AC is proven. Both await owner go-ahead (outward-facing).
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
1. Close SS-1.2 (SS-11) — the only open Stage-0 Story. Local plumbing is done and green locally; what
   remains is owner-gated and outward-facing: (a) make the initial commit (all files staged, none
   committed); (b) create a remote (GitHub) and push so Actions runs and the "green on push" AC is
   proven; (c) then move SS-11 In Progress -> In Review -> Done with an AC-check comment. Do NOT mark
   SS-11 Done until CI has actually run green on the remote.
2. Board moves: DONE this session. SS-1.6/1.8/1.9 are Done (Backlog -> To Do -> In Review -> Done, AC
   comments posted); SS-1.7 was already Done. Nothing else to transition until SS-11 closes.
3. Then Stage 0 closes and Stage 1 (ingestion + RAG core) begins, eval-first: no feature code before the eval it must pass exists.
