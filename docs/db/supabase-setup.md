# Running Sprintsight against a real Supabase database

Plain-English summary: the app's database code is tested fully offline (CI uses a throwaway
Postgres container). To run it against a real, always-on database you create a Supabase project
(Supabase is a managed cloud Postgres provider), put its connection string in a local .env file,
then run three commands: migrate, ingest, and a read-back check. Everything here uses SYNTHETIC
data. No real customer data is involved.

## One-time setup

Install the database extra editable, so the scripts run your working tree:

    pip install -e '.[db]'

## Provision (you do this once; it needs your account)

1. Create a Supabase project in a UK or EU region (residency, per ADR-0002).
2. In the SQL editor or Database settings, enable the `pgvector` extension (it stores the
   embedding vectors used for semantic search).
3. Copy the database connection string (the "URI" form, starting `postgresql://`). Make sure it
   requires TLS by appending `?sslmode=require` if it is not already there.
4. Put it in a local `.env` file at the repo root (this file is gitignored, never committed):

       DATABASE_URL=postgresql://...your-connection-string...?sslmode=require

   The app auto-loads `.env`. A real `export DATABASE_URL=...` in your terminal still wins over
   the file, and CI is unaffected.

## Load (run these three, in order, from the repo root)

    python scripts/migrate.py          # apply the schema
    python scripts/ingest.py           # load the 37-artifact synthetic corpus
    python scripts/retrieve_smoke.py   # a fresh process reads a cited chunk back

Expected: `migrate.py` prints `RESULT applied 1 migration(s)`; `ingest.py` prints a `RESULT`
line with `"db_artifact": 37`; `retrieve_smoke.py` exits 0 and prints a single `OK` summary
line confirming ranked results with provenance (the top `source_ref`). Because
`retrieve_smoke.py` is a separate process from `ingest.py`, a successful
read proves the data persisted and survives a restart.

## Re-running is safe

`ingest.py` is idempotent (keyed on a content hash). A second run reports `"ingested": 0` and
skips the existing rows, so you can re-run it without duplicating data.

`migrate.py` is a ONE-TIME step: re-running it after the schema already exists will report a
clean error message (class and text only, no raw password) and exit, so only run migrate once
per database.

## Security notes

- Synthetic data only; encryption-at-rest is provided by Supabase (ADR-0002).
- `DATABASE_URL` holds your database password. It lives only in `.env` (gitignored) and is never
  logged. Check it is set without printing it: `python -c "import os;print('set' if os.getenv('DATABASE_URL') else 'MISSING')"`.
- Require TLS (`sslmode=require`).
- A dedicated least-privilege database role is a documented follow-on (the first load may use the
  default role).
