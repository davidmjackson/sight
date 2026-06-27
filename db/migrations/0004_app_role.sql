-- Sprintsight migration 0004 — least-privilege application role (activates RLS, slice 7)
-- Slice 6 (0003) added the per-tenant RLS policy, but RLS is bypassed by SUPERUSERS and the table
-- OWNER. The app currently connects as the `postgres` owner, so the policy does not yet protect it.
-- This creates a NORMAL, least-privilege login that IS subject to RLS; pointing the app's
-- DATABASE_URL at it is what turns tenant isolation on for real.
--
-- NO PASSWORD here (secrets never live in git). The role is created NOLOGIN; the operator/CI grants
-- `LOGIN PASSWORD` out of band (see docs/db/app-role.md). NOSUPERUSER + NOBYPASSRLS + non-owner =>
-- the migration-0003 policy applies to it.
--
-- Idempotent: the role is guarded by an existence check; re-granting privileges is a no-op.

begin;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_rw') then
    create role app_rw nologin nosuperuser nobypassrls noinherit;
  end if;
end $$;

-- Least privilege: CRUD on the app tables + schema usage. No DDL, no role admin, no superuser.
grant usage on schema public to app_rw;
grant select, insert, update, delete on all tables in schema public to app_rw;

-- Cover tables created by later migrations too (objects the migration owner creates from now on).
alter default privileges in schema public
  grant select, insert, update, delete on tables to app_rw;

commit;
