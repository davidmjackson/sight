# Plan — slice 6: per-tenant RLS policies

Spec: docs/superpowers/specs/2026-06-27-tenant-rls-policies-design.md
Branch: realwiring-tenant-rls

Option A (FORCE RLS on the owner + a GUC-driven policy). Enforcement is provable only against real
Postgres, so the primary eval is the CI `db` job; offline pytest pins the app-side wiring.

1. **App-wiring test first (red)** — `tests/test_tenant_guc.py` (3): both `PostgresStore` and
   `PostgresRetriever` must issue `set_config('app.tenant_id', <tenant>, false)` on connect (faked
   `psycopg.connect`, no real DB).

2. **App wiring (green)** — add the `set_config` call right after `psycopg.connect(...)` in both
   stores' `__init__` (session-level GUC; correct under `autocommit=True`).

3. **Migration** — `db/migrations/0003_tenant_rls_policies.sql`: loop over the 8 tenant tables,
   `FORCE ROW LEVEL SECURITY` + a `tenant_isolation` policy (`USING` + `WITH CHECK` on
   `tenant_id = current_setting('app.tenant_id', true)::uuid`). Idempotent.

4. **Enforcement eval (CI)** — `db/checks/rls_isolation.sql`: seed a tenant-B team, prove A can't
   see B (and sees its 5 teams / 37 artifacts), B sees only its 1 row, unset GUC sees 0, then
   cleanup. Wire into the CI `db` job as a new step. Update the existing "Verify rows" psql session
   to set the tenant GUC first (FORCE RLS hides rows from an un-GUC'd session — itself proof the
   policy bites). Goes RED without 0003, GREEN with it.

5. **Verify** — offline suite + ruff + deterministic eval gates locally (293 passed + 4 skipped,
   ruff clean, gates unchanged); then push the branch and confirm the CI `db` job is GREEN (the
   real RLS proof — no local Postgres available); then an independent review; then merge.

## Operator step (live)
Apply migration 0003 to the live Supabase (DDL only). The app keeps connecting as `postgres` and
now sets the GUC automatically, so ingest/retrieval are unaffected. A raw psql/dashboard session
must `set app.tenant_id = '<uuid>';` to see rows (documented in the migration header).

## Deferred (slice 7)
Least-privilege non-owner DB role (Option B): create `app_rw`, grant least privilege, operator
switches the live `DATABASE_URL` to it; then FORCE can be dropped (a non-owner is subject to RLS
anyway). The policy + GUC wiring here are unchanged by that swap.
