# Design: Persistent Supabase (real-wiring slice 1)

Date: 2026-06-26
Stage: 7+ (real-wiring arc), Epic SS-5 area
Status: APPROVED (brainstorm) — pending implementation plan

## Plain-English summary (read this first)

Right now the app forgets everything when it restarts. It reads the synthetic corpus from
files in memory, and the only database it has ever used is the throwaway one in CI (the
automated test runner). This slice makes the app persist its data into a real, always-on
Supabase database (Supabase is a managed cloud Postgres provider), so the data survives a
restart, the same way a real product would.

The clever part: almost none of this is new code. The database code path already exists and
is already tested in CI against a local Postgres container. The one missing piece is small:
a loader that lets a normal run find its database settings without you having to retype them
into every terminal. Everything else is reuse plus one human step (you create the Supabase
project, because it needs your account and a secret; I wire it up and run the load).

Data stays SYNTHETIC. No real customer data ever touches this. That keeps our locked
security stance intact.

## Goal

Make a normal (non-CI) run find its database config and persist the synthetic corpus into a
real Supabase Postgres + pgvector instance, proven to survive a restart. (pgvector is the
Postgres extension that stores the embedding vectors used for semantic search.)

## Why this slice first

It is the foundation the rest of the "harden for real use" arc stands on. Real auth uses
Supabase Auth; the real embedder's vectors get stored here; the `team_id` column lives here.
Do this first and the other slices have somewhere to live. It is also the single biggest jump
in "feels like a real product": surviving a restart.

## What already exists (so we do NOT rebuild it)

- `db/migrations/0001_init.sql` — the full schema (artifact, chunk with a vector(1024) column, etc.).
- `sprintsight/ingest/store.py` — `PostgresStore` (psycopg, lazy import). Its docstring already
  says it is for "deployment against Supabase".
- `sprintsight/retrieval/retriever.py` — `PostgresRetriever` (pgvector `<=>` similarity).
- `scripts/ingest.py` — ingests the 37-artifact synthetic corpus into the store (idempotent on
  content_hash).
- `scripts/retrieve_smoke.py` — a retrieval smoke check.
- The CI `db` job (`.github/workflows/ci.yml`) — already runs migrate -> ingest -> idempotent
  re-ingest -> verify rows/embeddings against a local `pgvector/pgvector:pg16` container. This is
  the existing eval for the persistence logic and stays unchanged.

The DB scripts read `DATABASE_URL` straight from the environment. There is no loader, so a real
run only works if you `export DATABASE_URL=...` in every terminal (the same per-terminal pain we
hit with the connector demo).

## In scope

1. A small `.env` loader (the only new app code) + its tests.
2. A tiny `scripts/migrate.py` so provisioning needs no separate psql client.
3. A provisioning runbook: `docs/db/supabase-setup.md`.
4. A live-verified load into a real Supabase instance.

## Out of scope (clean follow-ons, named so they are not forgotten)

- Switching the web screens to read artifacts from the DB (that is Approach B; today the
  portfolio/report screens still read corpus files and that is unchanged here).
- The real embedder (D1) — this slice still uses `HashingEmbedder`.
- Real Supabase Auth + CSRF.
- Populating `team_id`.
- A dedicated least-privilege database role (flagged in Security; documented as a next step).

## Components

### 1. The `.env` loader — `sprintsight/config.py`

One function, `load_env(path=".env")`:

- If the file is absent: do nothing (fail-safe; CI and fresh checkouts are unaffected).
- Parse simple `KEY=value` lines; ignore blank lines and `#` comments; strip surrounding quotes.
- DO NOT override variables already present in `os.environ`. A real `export` in the terminal and
  CI's injected `DATABASE_URL` always win over the file. This guarantees CI behaviour cannot
  change and lets a user override the file ad hoc.
- Never print or log values (no secret leakage).
- No new dependency: a ~20-line stdlib parser, matching the project's habit of avoiding deps
  (like the stdlib PBKDF2 choice for auth) rather than pulling in `python-dotenv`.

Wired in at three entry points, called once before anything reads `os.environ`:
- `create_app()` in `sprintsight/web/app.py`
- the top of `scripts/ingest.py`
- the top of `scripts/retrieve_smoke.py`

### 2. `scripts/migrate.py` (tiny new runner)

Applies `db/migrations/*.sql` in filename order against `DATABASE_URL`, reusing the `psycopg`
dependency we already have, so the user does not need a separate psql client installed. Pure
ordering/arg logic is unit-testable; the actual apply runs against Postgres.

### 3. `docs/db/supabase-setup.md` (provisioning runbook)

Mirrors `docs/connectors/live-run.md`. The human-in-the-loop split:

You provision (needs your account + a secret); I wire and run:
1. Create a Supabase project in a UK/EU region; enable the `pgvector` extension; copy the
   connection string into `.env` as `DATABASE_URL=...` (`.env` is already gitignored).
2. `python scripts/migrate.py` — apply the schema.
3. `python scripts/ingest.py` — load the 37-artifact synthetic corpus.
4. `python scripts/retrieve_smoke.py` — a fresh process reads a cited chunk back, proving it
   persisted and survives a restart.

## Data flow

```
.env (DATABASE_URL)  --load_env-->  os.environ
                                         |
scripts/migrate.py  --psycopg-->  Supabase Postgres (schema created)
scripts/ingest.py   --PostgresStore + HashingEmbedder-->  Supabase (37 artifacts + chunks + vectors)
scripts/retrieve_smoke.py (fresh process)  --PostgresRetriever-->  reads cited chunk back
```

The web app's portfolio/report screens are UNCHANGED this slice: they still compute from the
corpus files. (The DB becomes their source of truth in a later slice.)

## Error handling

- Missing `.env`: no-op (not an error).
- Malformed `.env` line: skip the line; do not crash the app over a stray line.
- Missing `DATABASE_URL` when a DB script runs: the script fails fast with a clear message
  ("DATABASE_URL not set; see docs/db/supabase-setup.md"), never a raw traceback.
- Supabase unreachable / TLS failure: the psycopg error surfaces with the connection target
  named (host only, never the password).

## Testing (eval-first)

The genuinely new code is the loader, so the loader's tests ARE the eval for this slice and are
written first:

- loads `KEY=value` from a file into `os.environ`
- does NOT override a variable already set in `os.environ`
- no-op when the file is absent
- ignores blank lines, `#` comments, and strips quotes
- never emits the value (assert nothing is printed/logged)
- `scripts/migrate.py`: applies files in correct order; clear error when `DATABASE_URL` missing

Unchanged and still the proof of the persistence logic:
- the CI `db` job (migrate -> ingest -> idempotent re-ingest -> verify 37 rows + non-null
  embeddings) against local pgvector. No real Supabase in CI.

Unchanged and still the CI gate:
- deterministic watermelon eval (4/4) and report eval (4/4).

## Security (new data-persistence decision — flagged per build principle)

- **Data at rest in managed cloud.** We now persist into Supabase Postgres (UK/EU,
  encryption-at-rest per ADR-0002). Synthetic data only; no real customer data, consistent with
  the locked "persist on anonymized/synthetic data" stance.
- **`DATABASE_URL` holds DB credentials.** It lives only in `.env` (gitignored). The loader never
  logs it. Real environment wins over the file, so secrets are never silently overridden.
- **Connection security.** Require TLS on the Supabase connection (`sslmode=require`).
- **Least privilege (follow-on, NOT done here).** The first load may use the default role for
  simplicity; a dedicated least-privilege DB role is a documented next step.

## Definition of done

- `load_env` + tests green; wired into the web app and the two DB scripts.
- `scripts/migrate.py` + test green.
- `docs/db/supabase-setup.md` written.
- Live-verified: a real Supabase instance migrated + loaded (37 artifacts), and
  `retrieve_smoke.py` reads a cited chunk back in a fresh process (restart-survival proven).
- Full suite + ruff clean; watermelon 4/4, report 4/4, cross-tool 7/7 unchanged.
- HANDOVER + memory updated; logged as a new Jira Story under Epic SS-5 (the active stage), walked
  through the board states per workflow.md.
