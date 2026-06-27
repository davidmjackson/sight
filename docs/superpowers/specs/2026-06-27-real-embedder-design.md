# Design: Real embedder (real-wiring slice 2, decision D1)

Date: 2026-06-27
Stage: 7+ (real-wiring arc), Epic SS-5 area
Status: APPROVED (autonomous brainstorm; David delegated the decision gates) — pending plan

## Plain-English summary (read this first)

Today the app turns text into "embeddings" (lists of numbers that capture meaning, used for
semantic search) with a stand-in called `HashingEmbedder`. That stand-in is deliberately fake:
it hashes the words, so two pieces of text only look "similar" to it if they share the exact
same words. It has no idea that "the API integration is blocked" and "we are stuck on the
third-party endpoint" mean the same thing. It exists so every test runs offline with no model
to download.

This slice swaps in a REAL embedding model so search works by meaning, not by exact words. We
keep the fake as the default for the automated test runner (CI), and turn the real model on with
a switch, exactly the offline-by-default pattern we have reused for the database, the LLM writer,
the judge, and the live connectors.

Data stays SYNTHETIC. The model we choose runs on our own machine (in-region, self-hostable), so
no text is sent to an outside company. That keeps our locked security stance intact.

## Goal

Replace `HashingEmbedder` with a real, self-hostable, 1024-dimension embedding model behind the
existing `Embedder` seam, switched on by a fail-safe gate, and prove that real semantic search
retrieves a chunk the exact-match stand-in would miss. CI stays offline and deterministic.

## Why this model / approach (the decision gates, resolved)

David asked me to decide the gates and proceed. The decisions and their reasons:

1. **Self-hostable local model, not an external embeddings API (Voyage / OpenAI).**
   The schema (`db/migrations/0001_init.sql`: `embedding vector(1024)`) and the embedder docstring
   both already pre-commit decision D1 as "a self-hostable, in-region model with a fixed 1024-dim
   output". Honouring that keeps us aligned with the project's security-first / least-data / ZDR
   principles: no synthetic-or-otherwise text egresses to a third-party embeddings vendor, and no
   new vendor key. It also keeps the locked `vector(1024)` column unchanged, so NO schema migration.

2. **Default model: `thenlper/gte-large`** (1024-dim native output).
   Picked over `BAAI/bge-large-en-v1.5` (also 1024-dim) because gte-large does NOT require a
   query/passage instruction prefix, so the existing single-method `Embedder` seam
   (`embed(texts) -> list[list[float]]`) stays unchanged. bge would need asymmetric query vs
   passage handling, splitting the seam for no MVP benefit. The model id is configurable via env so
   we can swap it later under eval without code change.

3. **Library: `sentence-transformers`**, in a new optional `[embed]` pyproject extra, imported
   lazily (same pattern as psycopg in `[db]` and Composio in `[connectors]`). CI never installs it.

4. **Selection via a fail-safe `make_embedder()` factory** read from env. Default `hashing`
   (the stand-in); `SPRINTSIGHT_EMBEDDER=local` selects the real model. The scripts (`ingest.py`,
   `retrieve_smoke.py`) call the factory so the SAME embedder is used for ingest and query.

## The one correctness trap (must be documented + guarded)

Embeddings are only comparable if the SAME model produced both the stored chunk vectors and the
query vector. If you ingest with `HashingEmbedder` but query with `LocalEmbedder` (or change the
model id between ingest and query), every similarity score is meaningless and retrieval silently
returns garbage. The env-driven factory makes both sides read one setting, so as long as the same
`SPRINTSIGHT_EMBEDDER` (and model id) are set for the ingest run and the query run, they match. The
runbook calls this out explicitly: change the embedder, re-ingest.

## Eval-first (the heart of the slice)

New eval: **semantic retrieval beats lexical.** A small fixture of paraphrased queries that share
few or no words with their target chunk but match it in meaning.

- **CI gate (deterministic, always runs):** assert the GAP exists — with `HashingEmbedder` the
  paraphrase recall is at/under a low bar (it is exact-match only). This locks the motivation and
  proves the retrieval mechanism is wired; it is the failing-baseline half of red/green and stays
  in CI with no model download.
- **Live proof (gated, skipped in CI):** with the real `LocalEmbedder`, assert paraphrase recall
  clears a high bar. Skipped unless `sentence-transformers` is importable AND
  `SPRINTSIGHT_EMBEDDER=local`. This is the LIVE-VERIFIED half, run by hand (or in a model-enabled
  env), never a CI gate. Mirrors how every live path in this project is gated.

Plus a seam-contract test that needs NO model download: `make_embedder()` returns `HashingEmbedder`
by default and `LocalEmbedder` when gated; importing the module without `sentence-transformers`
does not crash (the dependency is imported lazily, with a friendly error only when `.embed()` is
first called without the extra installed).

## In scope

1. `LocalEmbedder` (lazy `sentence-transformers`, 1024-dim, normalized) + `make_embedder()` factory.
2. New `[embed]` pyproject extra.
3. Wire `scripts/ingest.py` + `scripts/retrieve_smoke.py` to the factory (same embedder both sides).
4. The new semantic-vs-lexical eval (CI baseline + gated live leg) + the seam-contract tests.
5. A short runbook: `docs/embedder/real-embedder.md` (the one-command live run + the re-ingest trap).
6. Live verification if the environment can pull the model; otherwise ship built+gated with the
   runbook (a project-consistent outcome, several prior slices shipped this way).

## Out of scope (deferred)

- Re-embedding the live Supabase corpus end-to-end is its own action (needs the model pulled in the
  target env); the slice wires it, the runbook drives it.
- A vector (HNSW) index on the chunk table (deferred in 0001 until recall/row-counts are known).
- Switching the web screens onto DB reads (real-wiring slice 4) and `team_id` (slice 3) are separate.
- Changing the graph builder / web default off `HashingEmbedder` (CI + offline demos keep the stand-in).
