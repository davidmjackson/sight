-- Slice 6 enforcement eval: proves the per-tenant RLS policy (migration 0003) actually isolates
-- tenants. Run in CI's `db` job AFTER ingest (so tenant A holds the 5 real teams).
--
-- IMPORTANT: RLS is bypassed by SUPERUSERS and by the table OWNER unless FORCEd — and even FORCE
-- does not subject a superuser. CI's `postgres` user is a superuser, so we must run the checks as a
-- NON-superuser, NON-owner role to exercise the policy at all. This is also the real lesson: the app
-- gains protection only when it CONNECTS as such a least-privilege role (Option B, the next slice);
-- connecting as the superuser/owner bypasses RLS.
--
-- Goes RED without migration 0003: a non-owner with RLS enabled (0002) but NO policy sees ZERO rows,
-- so "tenant A should see 5 teams" fails. GREEN with 0003's policy. Run with ON_ERROR_STOP=1.
\set tenant_a '00000000-0000-0000-0000-000000000001'
\set tenant_b '00000000-0000-0000-0000-000000000002'

-- A non-superuser, non-owner role that IS subject to RLS. Idempotent re-create.
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'rls_probe') then
    execute 'drop owned by rls_probe';
    execute 'drop role rls_probe';
  end if;
end $$;
create role rls_probe nologin;
grant usage on schema public to rls_probe;
grant select, insert, delete on team to rls_probe;

set role rls_probe;

-- Seed one team for tenant B. WITH CHECK ties the insert to the connection's current tenant, so a
-- connection cannot plant another tenant's data.
select set_config('app.tenant_id', :'tenant_b', false);
insert into team (key, name, tenant_id) values ('ZZ-Isolation', 'Isolation Probe', :'tenant_b'::uuid);

-- As tenant A: must NOT see tenant B's probe, and must still see exactly the 5 real teams.
select set_config('app.tenant_id', :'tenant_a', false);
do $$
begin
  if (select count(*) from team where key = 'ZZ-Isolation') <> 0 then
    raise exception 'RLS LEAK: tenant A can see tenant B''s team';
  end if;
  if (select count(*) from team) <> 5 then
    raise exception 'tenant A should see 5 teams, got % (policy missing or denying?)',
      (select count(*) from team);
  end if;
end $$;

-- As tenant B: sees only its 1 probe team and none of tenant A's.
select set_config('app.tenant_id', :'tenant_b', false);
do $$
begin
  if (select count(*) from team) <> 1 then
    raise exception 'tenant B should see exactly 1 team, got %', (select count(*) from team);
  end if;
end $$;

-- No tenant set: fail-closed, zero rows.
select set_config('app.tenant_id', null, false);
do $$
begin
  if (select count(*) from team) <> 0 then
    raise exception 'fail-closed broken: unset GUC should see 0 teams, got %',
      (select count(*) from team);
  end if;
end $$;

-- Cleanup the probe row (delete is itself RLS-scoped, so re-assert B's tenant first).
select set_config('app.tenant_id', :'tenant_b', false);
delete from team where key = 'ZZ-Isolation';
reset role;
select set_config('app.tenant_id', null, false);

\echo 'RLS isolation check passed'
