-- Sprintsight migration 0001 — Stage-1 core (SS-2.4 / SS-1.9)
-- Subset of docs/schema/schema-design.md: Group 2 (delivery domain), Group 3 (source corpus),
-- Group 5 (signals). RAID/risk-findings, outputs, and the event log land in later migrations.
-- Single-tenant: tenant_id present on every domain table (decision D2) but NOT enforced (no RLS).
-- Apply on Postgres with the pgvector extension available.

begin;

create extension if not exists vector;

-- Enums used by the Stage-1 subset (others declared when their groups land).
create type rag_status        as enum ('red', 'amber', 'green');
create type dependency_status as enum ('open', 'at_risk', 'slipped', 'resolved');
create type source_type       as enum ('jira', 'confluence', 'slack', 'raid', 'other');
create type signal_type       as enum ('burn_ratio', 'velocity_decline', 'carry_over_growth',
                                       'flat_burndown', 'dependency_slip', 'raid_gap');

-- ---------- Group 2: delivery domain ----------

create table team (
  id          uuid primary key default gen_random_uuid(),
  key         text not null,                 -- Atlas | Boreas | Cygnus | Draco
  name        text not null,
  tenant_id   uuid not null,
  created_at  timestamptz not null default now(),
  unique (tenant_id, key)
);

create table sprint (
  id            uuid primary key default gen_random_uuid(),
  team_id       uuid not null references team (id) on delete cascade,
  sprint_number int  not null,
  start_date    date not null,
  end_date      date not null,
  reported_rag  rag_status not null,         -- the team's own green/amber/red claim
  tenant_id     uuid not null,
  unique (team_id, sprint_number)
);

-- ---------- Group 3: source corpus (provenance baked in) ----------
-- Declared before `dependency` because dependency.discovered_from_artifact_id references it.

create table artifact (
  id               uuid primary key default gen_random_uuid(),
  source_type      source_type not null,
  source_ref       text not null,            -- Jira key, Confluence page id, Slack ts, ...
  title            text,
  body             text not null,
  author           text,
  source_timestamp timestamptz,
  team_id          uuid references team (id) on delete set null,
  ingested_at      timestamptz not null default now(),
  content_hash     text not null,            -- dedupe + integrity
  tenant_id        uuid not null,
  unique (tenant_id, source_type, source_ref)
);

create index on artifact (content_hash);

create table chunk (
  id          uuid primary key default gen_random_uuid(),
  artifact_id uuid not null references artifact (id) on delete cascade,
  ordinal     int  not null,
  text        text not null,
  char_start  int  not null,
  char_end    int  not null,
  token_count int,
  embedding   vector(1024),                  -- D1: dimension locked at 1024
  tenant_id   uuid not null,
  unique (artifact_id, ordinal)
);
-- Vector (HNSW) index deferred until row counts and recall are known (Stage 1, under eval).

-- Back to Group 2: dependency (B1 guardrail — only discoverable links are stored).

create table dependency (
  id                          uuid primary key default gen_random_uuid(),
  from_team_id                uuid not null references team (id) on delete cascade,
  to_team_id                  uuid not null references team (id) on delete cascade,
  description                 text not null,
  status                      dependency_status not null default 'open',
  discovered_from_artifact_id uuid references artifact (id) on delete set null,
  tenant_id                   uuid not null,
  created_at                  timestamptz not null default now()
);

create table sprint_metric (
  id                uuid primary key default gen_random_uuid(),
  sprint_id         uuid not null references sprint (id) on delete cascade,
  committed_points  numeric not null,
  completed_points  numeric not null,
  carry_over_points numeric not null,
  velocity          numeric,
  tenant_id         uuid not null,
  unique (sprint_id)
);

create table burndown_snapshot (
  id               uuid primary key default gen_random_uuid(),
  sprint_id        uuid not null references sprint (id) on delete cascade,
  day              int  not null,            -- day index within the sprint
  remaining_points numeric not null,
  tenant_id        uuid not null,
  unique (sprint_id, day)
);

-- ---------- Group 5: signals (the explainable watermelon) ----------

create table signal (
  id                  uuid primary key default gen_random_uuid(),
  team_id             uuid not null references team (id) on delete cascade,
  sprint_id           uuid references sprint (id) on delete cascade,
  signal_type         signal_type not null,
  computed_value      jsonb not null,        -- numeric or structured, by type
  reference_threshold text,                  -- the number/rule used, shown to the user
  reference_window    text,                  -- e.g. "2 sprints"
  breached            boolean not null default false,
  computed_at         timestamptz not null default now(),
  tenant_id           uuid not null
);

commit;
