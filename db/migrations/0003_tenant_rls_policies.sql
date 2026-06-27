-- Sprintsight migration 0003 — per-tenant Row Level Security POLICIES (DB hardening, slice 6)
-- Migration 0002 enabled RLS with NO policies (shut the public PostgREST door). This adds the
-- actual tenant-isolation policy so the DB enforces the boundary independently of the app's
-- WHERE clauses (defense-in-depth): a query that forgot to scope by tenant cannot leak rows.
--
-- The app announces its tenant once per connection via
-- `select set_config('app.tenant_id', <uuid>, false)` (see PostgresStore/PostgresRetriever); the
-- policy reads it with missing_ok=true, so an UNSET GUC yields NULL -> no rows -> fail-closed.
--
-- IMPORTANT — who is actually subject to this policy: RLS is BYPASSED by SUPERUSERS and by the
-- table OWNER. FORCE ROW LEVEL SECURITY (below) subjects the *owner*, but it does NOT subject a
-- superuser. So a connection as a superuser/owner (e.g. CI's `postgres`) still bypasses RLS. The
-- policy genuinely protects only a NON-superuser, NON-owner role. Therefore real app enforcement
-- requires the app to CONNECT as a least-privilege role (Option B, the next slice); this migration
-- ships the correct, proven policy + the GUC wiring so that switch is the only remaining step.
-- The CI eval (db/checks/rls_isolation.sql) proves isolation by running as such a probe role.
--
-- Idempotent: FORCE is a no-op when already set; DROP POLICY IF EXISTS precedes each CREATE.
-- Operator note: with FORCE RLS, a raw psql/Supabase-dashboard session as postgres must
--   `set app.tenant_id = '<uuid>';` to see rows. DDL/migrations are unaffected (RLS filters rows).

begin;

do $$
declare
  t text;
  tables text[] := array[
    'team', 'sprint', 'artifact', 'chunk',
    'dependency', 'sprint_metric', 'burndown_snapshot', 'signal'
  ];
begin
  foreach t in array tables loop
    execute format('alter table %I force row level security', t);
    execute format('drop policy if exists tenant_isolation on %I', t);
    execute format(
      'create policy tenant_isolation on %I '
      'using (tenant_id = current_setting(''app.tenant_id'', true)::uuid) '
      'with check (tenant_id = current_setting(''app.tenant_id'', true)::uuid)',
      t
    );
  end loop;
end $$;

commit;
