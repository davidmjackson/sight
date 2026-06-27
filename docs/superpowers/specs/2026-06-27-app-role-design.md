# Slice 7 — least-privilege app DB role (activates RLS enforcement, Epic SS-5)

Plain-English summary (read this first)
---------------------------------------
Slice 6 added the per-tenant rule (RLS policy) to the database, but discovered the rule does NOT
apply to a superuser or the table owner. The app currently logs into the database as the owner
(`postgres`), so the rule does not yet protect it. This slice creates a normal, least-privilege
login (`app_rw`) that CAN do only what the app needs (read/write the app tables, nothing more) and
IS subject to the rule. Pointing the app at this login is what finally turns tenant isolation on
for real. We prove it in CI by running the actual app (ingest + retrieval) as `app_rw` and showing
it sees zero rows without a tenant set and the right rows with one.

In scope
--------
1. `db/migrations/0004_app_role.sql`: create role `app_rw` (NOSUPERUSER, NOBYPASSRLS, NOLOGIN — so
   it is subject to RLS), grant it least privilege (USAGE on schema, SELECT/INSERT/UPDATE/DELETE on
   the app tables, plus matching default privileges for future tables). **No password in git** —
   the operator/CI adds `LOGIN PASSWORD` separately.
2. CI `db` job proves the production path end-to-end: enable an `app_rw` login with a CI-only
   password, run ingest + retrieval **as `app_rw`** (not as the owner), and assert `app_rw` is
   subject to RLS — zero rows with no tenant GUC set (fail-closed), the demo tenant's rows with it.
   This is the enforcement proof slice 6 could not give (it used a throwaway probe; here the real
   app role + real app code path are exercised).
3. `docs/db/app-role.md`: the operator runbook to create + switch to `app_rw` on the live Supabase.

No application code change: `PostgresStore`/`PostgresRetriever` already set the `app.tenant_id` GUC
on connect and read `DATABASE_URL`; connecting as `app_rw` is purely a credential (URL) change.

Out of scope (named, not forgotten)
-----------------------------------
- The live Supabase switch itself (operator step: create the role + password, grant, repoint
  `DATABASE_URL`, verify via the session pooler). CI proves the role/grants/RLS logic.
- Scoping the policy `TO app_rw`: deliberately NOT done. Slice 6's policy applies to PUBLIC and
  already denies the PostgREST anon/authenticated roles (they cannot set the GUC -> NULL -> 0 rows).
  Scoping `TO app_rw` would instead lock the `postgres` owner out of its own tables entirely (0 rows
  even for admin/dashboard/migrations reads), which is worse. The PUBLIC policy + this role is the
  cleaner end state.
- Per-tenant provisioning / multi-tenant users (still single-tenant `DEMO_TENANT_ID`).
- A separate read-only role — `app_rw` is the single app role for the showcase.

Design
------
### `db/migrations/0004_app_role.sql`
```
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'app_rw') then
    create role app_rw nologin nosuperuser nobypassrls noinherit;
  end if;
end $$;
grant usage on schema public to app_rw;
grant select, insert, update, delete on all tables in schema public to app_rw;
alter default privileges in schema public
  grant select, insert, update, delete on tables to app_rw;
```
Idempotent (role guarded by existence check; re-granting is a no-op). NOLOGIN + no password keeps
the migration secret-free; the operator/CI grants `LOGIN PASSWORD` out of band.

### Why this activates enforcement
`app_rw` is NOSUPERUSER + NOT the table owner + NOBYPASSRLS, so the migration-0003 policy applies
to it. The app sets `app.tenant_id` on connect, so its queries see exactly its tenant; a forgotten
WHERE (or an unset GUC) yields zero rows, not a leak.

Security
--------
Least privilege: `app_rw` gets only CRUD on the app tables and USAGE on the schema — no DDL, no role
management, no superuser. The password lives only in the deployment's secret store (`.env` /
Supabase), never in git. RLS now genuinely constrains the app's own connection.

Eval-first
----------
Enforcement is provable only against real Postgres, so the eval is the CI `db` job: it runs the real
ingest + retrieval as `app_rw` and asserts RLS is active for that role (0 rows without the GUC, the
demo tenant's rows with it). Goes RED if `app_rw` were over-privileged (e.g. BYPASSRLS) or the
grants were wrong. Deterministic watermelon/report/cross-tool gates unchanged. Verified on a branch
via CI before merge (no local Postgres).
