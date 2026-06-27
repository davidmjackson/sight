# Design: Populate artifact.team_id (real-wiring slice 3)

Date: 2026-06-27
Stage: 7+ (real-wiring arc), Epic SS-5 area
Status: APPROVED (autonomous brainstorm; David delegated the decision gates) — pending plan

## Plain-English summary (read this first)

The database has a `team` table and every artifact has a `team_id` column meant to point at the
team it belongs to. Right now that column is always empty (NULL): we never create the team rows and
never set the link. So the database cannot answer "show me only Atlas's stuff", even though the app
can do that in memory off the synthetic corpus.

This slice fills that gap: create the five team rows (Atlas, Boreas, Cygnus, Draco, Echo) and set
each artifact's `team_id` when it is ingested, then switch on team filtering in the database search
(the production retriever's own note says this was "awaiting team_id population"). Small, plumbing-only,
synthetic data. It is the prerequisite for the next two slices (reading the screens from the DB, and
per-team security rules).

## Goal

Populate `team` rows and `artifact.team_id` during ingestion, and enable an optional team filter in
`PostgresRetriever`, proven by an eval. CI stays deterministic; the schema is unchanged.

## Decisions (the gates, resolved)

1. **Resolve teams up front in the pipeline, not inside the artifact upsert.** `ingest_corpus`
   collects the distinct team keys, calls `store.upsert_team(key, name)` once each to get their ids,
   then sets `ArtifactInput.team_id`. Keeps the store dumb (it just writes what it is given) and the
   pipeline orchestrating, matching the existing separation. `upsert_team` is idempotent on
   `(tenant_id, key)`.
2. **team key == corpus team string; name == same.** The corpus has no separate display name; the
   synthetic teams are "Atlas".. so key and name are both that. (A real loader can split them later.)
3. **Enable team scoping in `PostgresRetriever` now** (optional `team` param + return the team key),
   so `team_id` is actually USED this slice, not a dormant column. The in-memory retriever already
   scopes by team; this brings the DB path level and gives the eval something concrete to assert.
4. **No new delivery-domain loading** (sprint / metric / burndown / dependency / signal rows) — that
   is a separate, larger slice. This one is teams + the artifact link only.

## The subtlety to document (same shape as slice 2's trap)

Ingestion skips an artifact whose (embedder + body) hash is unchanged. So on a database that already
holds the 37 artifacts with NULL `team_id` (the live Supabase from slice 1), a plain re-ingest would
SKIP them all and never backfill the link. This is not a problem in practice because the slice-2 real
embedder change already forces a full re-ingest of that same DB (the embedder signature changed), and
`team_id` is set on that pass. So the live backfill rides along with the real-embedder re-ingest the
operator already has to run. A fresh DB (CI, or a re-provisioned Supabase) gets `team_id` on its first
ingest. The runbook states this explicitly.

## Eval-first

- **CI gate (deterministic, pytest, no DB):** after `ingest_corpus(InMemoryStore())`, assert exactly
  5 teams exist, every artifact carries a non-NULL `team_id`, and a sampled artifact's `team_id`
  resolves to the correct team key. This locks "team_id is populated and correct".
- **DB proof (CI `db` job, real Postgres):** extend the verify step to assert all 37 artifacts have a
  non-NULL `team_id` and 5 team rows exist, and add a team-scoped retrieval check (a query scoped to
  one team returns only that team's chunks). Mirrors the existing `retrieve_smoke` pattern.

## In scope

1. `Store.upsert_team(key, name) -> str` on the protocol + both stores; `team_id` carried on artifact.
2. `ArtifactInput.team_id` (defaulted, back-compatible); pipeline resolves + passes it.
3. `counts()` adds `team`.
4. `PostgresRetriever` optional `team` filter + returns team key.
5. Eval: new pytest (in-memory) + extended CI `db` verify/scoping checks.
6. Runbook note on the live backfill via re-ingest.

## Out of scope (deferred)

- Loading sprint/metric/burndown/dependency/signal rows (their own slice).
- Switching the web screens / detector to read team from the DB (slice 4, Approach B).
- Per-tenant RLS policies keyed on team/tenant (slice 5).
