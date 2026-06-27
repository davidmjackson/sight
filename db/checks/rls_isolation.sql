-- Slice 6 enforcement eval: proves per-tenant RLS isolation (migration 0003).
-- Run in CI's `db` job as the `postgres` owner AFTER ingest (so tenant A holds the 5 real teams).
-- Goes RED without migration 0003 (no policy -> the GUC is ignored -> cross-tenant rows visible);
-- GREEN with it. Run with: psql -v ON_ERROR_STOP=1 -f db/checks/rls_isolation.sql
--
-- tenant A = the demo tenant the corpus is ingested under (store.DEMO_TENANT_ID).
\set tenant_a '00000000-0000-0000-0000-000000000001'
\set tenant_b '00000000-0000-0000-0000-000000000002'

-- Seed one team for tenant B. Needs B's GUC: WITH CHECK forbids inserting a row for a tenant
-- other than the connection's current one (so one connection cannot plant another tenant's data).
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
    raise exception 'tenant A should see 5 teams, got %', (select count(*) from team);
  end if;
  if (select count(*) from artifact) <> 37 then
    raise exception 'tenant A should see 37 artifacts, got %', (select count(*) from artifact);
  end if;
end $$;

-- As tenant B: sees only its 1 probe team and none of tenant A's rows.
select set_config('app.tenant_id', :'tenant_b', false);
do $$
begin
  if (select count(*) from team) <> 1 then
    raise exception 'tenant B should see exactly 1 team, got %', (select count(*) from team);
  end if;
  if (select count(*) from artifact) <> 0 then
    raise exception 'RLS LEAK: tenant B can see % of tenant A''s artifacts',
      (select count(*) from artifact);
  end if;
end $$;

-- No tenant set: fail-closed, zero rows everywhere.
select set_config('app.tenant_id', null, false);
do $$
begin
  if (select count(*) from team) <> 0 then
    raise exception 'fail-closed broken: unset GUC should see 0 teams, got %',
      (select count(*) from team);
  end if;
end $$;

-- Cleanup the probe (delete is itself RLS-scoped, so re-assert B's tenant first).
select set_config('app.tenant_id', :'tenant_b', false);
delete from team where key = 'ZZ-Isolation';
select set_config('app.tenant_id', null, false);

\echo 'RLS isolation check passed'
