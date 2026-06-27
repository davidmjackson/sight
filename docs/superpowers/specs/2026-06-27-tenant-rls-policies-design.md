# Slice 6 — per-tenant RLS policies (real-wiring / DB hardening, Epic SS-5)

Plain-English summary (read this first)
---------------------------------------
"RLS" = Row Level Security: the database itself filters which rows a query can see, based on a
rule, no matter what the query asks for. Today every table has a `tenant_id` column and our app
code always adds `WHERE tenant_id = ...`, but that is the app policing itself. If any query ever
forgot that clause (a bug, a new feature, a console session), it could read another tenant's data.

This slice makes the database enforce the boundary, so a forgotten `WHERE` cannot leak across
tenants. We add a policy on every tenant table: "you may only see rows whose `tenant_id` matches
the tenant set for this connection." The app announces its tenant once per connection (a Postgres
session setting), and the database does the rest.

Why this needs more than "enable RLS" (the slice-2-era hardening)
----------------------------------------------------------------
Migration 0002 already turned RLS *on* with NO policies (door shut for the public PostgREST API).
But the app connects as the `postgres` table owner, and **owners bypass RLS**, so policies alone do
nothing for the app. Two ways to make the app subject to its own policies:
- **A. `FORCE ROW LEVEL SECURITY`** on each table (the owner is no longer exempt). The app keeps
  connecting as `postgres`; it just has to announce its tenant per connection.
- **B. A dedicated least-privilege non-owner role** (e.g. `app_rw`) that the app connects as; a
  non-owner is subject to RLS without FORCE.

**Decision: A for this slice.** It is the lean, fully CI-verifiable choice with the smallest
operator burden (apply one DDL migration; no new role, no credential change). The policies + the
app-sets-its-tenant wiring built here are exactly what B needs too, so B (the production
least-privilege role) is a clean forward-compatible follow-on (slice 7): it only swaps the
connection role and drops FORCE. (Chosen 2026-06-27; B noted, not forgotten.)

**Correction discovered via CI (2026-06-27):** RLS is bypassed by SUPERUSERS and the table OWNER,
and `FORCE` subjects the owner but NOT a superuser. CI's `postgres` is a superuser, so it bypasses
the policy entirely — and the live Supabase app role may too. So Option A's policy is *correct and
proven* but does NOT actually protect the app while the app connects as the superuser/owner. Real
enforcement requires the app to connect as a NON-superuser, NON-owner least-privilege role —
i.e. Option B is not merely a "nicer" follow-on, it is REQUIRED to activate enforcement. This slice
therefore ships the proven policy + GUC wiring (enforcement-ready); slice 7 (the least-privilege app
role + the operator switching `DATABASE_URL` to it) flips it on with no further app code. The CI eval
proves the policy bites by running the isolation check as a non-superuser probe role (`SET ROLE`).

How the app announces its tenant
--------------------------------
A custom Postgres session setting (GUC) `app.tenant_id`. On connect, the app runs
`select set_config('app.tenant_id', <tenant>, false)` (session-level, correct because both stores
use `autocommit=True`). Policies read `current_setting('app.tenant_id', true)::uuid` (the `true` =
missing_ok, so an unset GUC yields NULL → `tenant_id = NULL` → no rows → **fail-closed**).

In scope
--------
1. `db/migrations/0003_tenant_rls_policies.sql`: on all 8 tenant tables (team, sprint, artifact,
   chunk, dependency, sprint_metric, burndown_snapshot, signal): `FORCE ROW LEVEL SECURITY` + a
   `tenant_isolation` policy with `USING` and `WITH CHECK` on
   `tenant_id = current_setting('app.tenant_id', true)::uuid`. Idempotent (FORCE is a no-op when
   set; `DROP POLICY IF EXISTS` before `CREATE`).
2. App wiring: `PostgresStore.__init__` and `PostgresRetriever.__init__` set the `app.tenant_id`
   GUC immediately after connecting (a shared one-liner), so every query/insert on that connection
   is tenant-scoped by the DB. This is what makes ingest + retrieval keep working under FORCE RLS.
3. The enforcement eval (CI `db` job, real Postgres): a committed `db/checks/rls_isolation.sql`
   that seeds a second tenant's row, then asserts tenant A cannot see tenant B's row (and vice
   versa) and that an unset GUC sees zero rows. It goes RED without migration 0003 (policies absent
   → cross-tenant rows visible) and GREEN with it. The existing "Verify rows" psql step is updated
   to set the GUC first (otherwise FORCE RLS hides every row from the un-GUC'd psql session — which
   is itself a proof the policy bites).
4. Offline pytest: assert both stores issue the `set_config('app.tenant_id', ...)` call on init
   (via a faked `psycopg.connect`), pinning the app-side wiring without a real DB.

Out of scope (named, not forgotten)
-----------------------------------
- The least-privilege non-owner DB role (Option B) — slice 7; needs role + grants + the operator
  switching the live `DATABASE_URL` to that role.
- Real multi-tenant provisioning (linking users → tenants, a tenant picker). Still single-tenant
  (`DEMO_TENANT_ID`); this slice proves + enforces the boundary mechanism, ready for multi-tenant.
- Per-tenant policies on future tables (RAID/outputs/event log) — add when those migrations land.

Security
--------
Defense-in-depth: the DB now enforces tenant isolation independently of the app's `WHERE` clauses.
Fails closed (no GUC → zero rows). No new secrets. Note for the operator: with FORCE RLS, a raw
`psql`/Supabase-dashboard session as `postgres` must `set app.tenant_id = '<uuid>'` to see rows
(more secure; documented in the runbook). DDL/migrations are unaffected (RLS filters rows, not DDL).

Eval-first
----------
Enforcement is provable only against real Postgres, so the eval is the CI `db` job + the committed
`rls_isolation.sql` (red without 0003, green with it) — the same "the db job is the DB proof"
pattern as prior DB slices. Offline pytest pins the app-side GUC wiring. Deterministic watermelon
(4/4) + report (4/4) + cross-tool (7/7) gates are untouched. Verified on a branch via CI before
merge (no local Postgres available).
