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
-- Operator notes:
--   * With FORCE RLS, a raw psql/Supabase-dashboard session must `set app.tenant_id = '<uuid>';`
--     to see rows. DDL/migrations are unaffected (RLS filters rows, not DDL).
--   * Deploy ORDER on the live DB: ship the GUC-setting app code FIRST, then apply this migration.
--     If the migration lands while pre-GUC code is live, those connections fail closed (0 rows /
--     WITH CHECK rejects writes) until redeploy — no leak, self-healing, but a brief outage.
--   * The app must use a SESSION-scoped connection (direct, or Supabase SESSION pooler :5432).
--     A transaction pooler (:6543) does not carry session GUCs to later statements -> 0 rows.
--   * Slice 7 (least-privilege role): scope this policy `TO <app_role>` so the PostgREST
--     anon/authenticated roles keep 0002's hard deny-by-default instead of this permissive policy.

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
    -- nullif(..., '') because set_config('app.tenant_id', NULL, ...) stores '' (empty string), not
    -- a true unset; without it an unset/cleared GUC would error on ''::uuid instead of failing
    -- closed. %L safely quotes the GUC name and the empty-string sentinel.
    execute format(
      'create policy tenant_isolation on %I '
      'using (tenant_id = nullif(current_setting(%L, true), %L)::uuid) '
      'with check (tenant_id = nullif(current_setting(%L, true), %L)::uuid)',
      t, 'app.tenant_id', '', 'app.tenant_id', ''
    );
  end loop;
end $$;

commit;
