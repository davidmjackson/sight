# Sprintsight

AI delivery-intelligence layer that reads across delivery tools (Jira, Confluence, Slack, RAID logs) and produces audience-tuned, fully-cited status reports, risk detection, and a watermelon detector (reported-green / actually-red). Part of Sprint Suite (sprintsuite.uk), accessed via the Suite tile with its own login.

## Status

Stage 0 (Foundation). Showcase-first, single-tenant, synthetic / anonymized data only. There is no application code yet: scaffolding and the ingestion + RAG core land in Stage 1. All Stage 0 specs are written and locked under `docs/`.

## Stack (locked)

- Backend: Python / FastAPI
- Orchestration: LangGraph (Stage 3+), raw Anthropic SDK where clearer
- LLM: Anthropic API (Claude), structured outputs, Zero Data Retention on all data traffic
- Data / RAG: Postgres + pgvector on managed Supabase (UK / EU region)
- Auth: Supabase Auth. Single-tenant for the showcase, roles admin / delivery_manager / viewer
- Evals + observability: Langfuse. Deterministic-first, LLM-as-judge deferred to Stage 4

## Repo layout

- `HANDOVER.md` — current state. Read first. Single source of truth for where we are.
- `CLAUDE.md` — build conventions and how to drive the Jira board (Claude Code's manual).
- `docs/` — specs and decisions:
  - `docs/data/` — scenario-first synthetic data strategy (four teams, two sprints)
  - `docs/evals/` — watermelon and report-quality eval specs
  - `docs/moat/` — the three methodology-aware behaviours
  - `docs/schema/` — base schema design (signed off)
  - `docs/adr/` — architecture decision records
  - `docs/jira/` — board workflow, epic-to-key map, issue export

## Local setup

1. Copy the environment template and fill in real values:

   ```
   cp .env.example .env
   ```

   `.env` holds real secrets and must never be committed. It is gitignored as part of Story SS-1.2.

2. Application scaffolding (FastAPI app, dependencies, CI) is not in place yet. It is the remaining Stage 0 plumbing (SS-1.2) plus early Stage 1 work.

## Principles

- Eval-first: no feature code before the eval it must pass exists.
- Security-first: least data, least privilege. Synthetic / anonymized data only for the showcase.
- Human-in-the-loop on anything that writes. RAID writes are recommend-only.

## Data and security

Single-tenant showcase on anonymized / synthetic sprint and RAID data, not real client data. Encryption at rest (managed Supabase UK / EU). ZDR on all Anthropic API traffic. Full audit / reasoning log.
