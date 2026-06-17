# SS-1.9 Base schema design

**Status:** SIGNED OFF. Decisions D1 to D5 locked 2026-06-17. Security review signed off 2026-06-17. SS-1.8 locked (ADR-0002), so encryption-at-rest is confirmed.
**Stage:** 0 (Foundation). Paper spec only. No migrations run until Stage 1 opens.
**Scope:** single-tenant showcase, on anonymized / synthetic data, ZDR on Anthropic API traffic.
**Store:** Postgres + pgvector. Identity sits on Supabase Auth (`auth.users`); we do not roll our own credentials.

This is the design artifact for SS-1.9. It defines tables, relationships, and the provenance / audit model. It does not run anything. Stage 1 turns the relevant parts into migrations, eval-first.

---

## Locked decisions

- **D1 Embedding model + vector dimension.** Self-hostable open model, run in-region, so chunk text never leaves the UK/EU boundary. Vector dimension fixed at **1024** (bge-large-en-v1.5 / e5-large family). The schema commits to the dimension only; the exact model is confirmed at Stage 1 under eval. Switching to a different-dimension model later is a migration, so 1024 is the commitment.
- **D2 tenant_id.** Present on every domain table. No RLS, no policies, no enforcement yet. This is the cheap half of "design multi-tenant, deploy single-tenant" and keeps the suite-identity door open.
- **D3 Reasoning-log depth.** `event.detail` holds references (ids) plus a short rationale string. Never raw prompt or response bodies. Honours ZDR and least-data; any step is reconstructable from the referenced ids without a second copy of client text.
- **D4 Role model.** Enum column on `app_user` (admin / delivery_manager / viewer). Promote to a roles table only if and when roles carry distinct permission sets.
- **D5 Citation granularity.** Chunk-level for v1. Character-span is available later for free because `chunk` already stores `char_start` / `char_end`.

---

## Conventions

- Primary keys: `uuid` default `gen_random_uuid()`.
- Timestamps: `timestamptz`.
- `tenant_id uuid not null` on every domain table (D2). No FK to a tenants table yet; single value for the showcase.
- Provenance is structural: every artifact carries `source_type` + `source_ref` + `content_hash`, and every derived record points back to the artifact or chunk it came from.
- Enums declared up front so the DDL reads cleanly.

```sql
create extension if not exists vector;

create type app_role          as enum ('admin', 'delivery_manager', 'viewer');
create type rag_status        as enum ('red', 'amber', 'green');
create type dependency_status as enum ('open', 'at_risk', 'slipped', 'resolved');
create type source_type       as enum ('jira', 'confluence', 'slack', 'raid', 'other');
create type raid_type         as enum ('risk', 'assumption', 'issue', 'dependency');
create type severity_level    as enum ('low', 'medium', 'high', 'critical');
create type finding_status    as enum ('suggested', 'accepted', 'dismissed');
create type signal_type       as enum ('burn_ratio', 'velocity_decline', 'carry_over_growth',
                                       'flat_burndown', 'dependency_slip', 'raid_gap');
create type audience          as enum ('team', 'programme', 'exec');
create type report_scope      as enum ('team', 'sprint', 'portfolio');
create type actor_type        as enum ('user', 'agent', 'system');
```

---

## Group 1: Identity and access

Supabase Auth owns credentials. `app_user` is the profile + role join, keyed to `auth.users.id`.

```sql
create table app_user (
  id            uuid primary key references auth.users (id) on delete cascade,
  display_name  text not null,
  role          app_role not null default 'viewer',
  tenant_id     uuid not null,
  created_at    timestamptz not null default now()
);
```

---

## Group 2: Delivery domain

The structured truth the watermelon detector runs on. `reported_rag` is the team's own claim; the signals (Group 5) are the computed reality. The gap between them is the watermelon.

```sql
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

create table dependency (
  id                        uuid primary key default gen_random_uuid(),
  from_team_id              uuid not null references team (id) on delete cascade,
  to_team_id                uuid not null references team (id) on delete cascade,
  description               text not null,
  status                    dependency_status not null default 'open',
  discovered_from_artifact_id uuid references artifact (id) on delete set null,
  tenant_id                 uuid not null,
  created_at                timestamptz not null default now()
);
```

Note: `dependency.discovered_from_artifact_id` is nullable and references `artifact`. It enforces the B1 guardrail at the data layer: a dependency is recorded only when it is discoverable from a real artifact. We do not store inferred links. (The FK is declared after `artifact` exists; in a single migration, create `artifact` first or add this FK in a follow-up statement.)

---

## Group 3: Source corpus (RAG, provenance baked in)

```sql
create table artifact (
  id               uuid primary key default gen_random_uuid(),
  source_type      source_type not null,
  source_ref       text not null,            -- e.g. Jira key, Confluence page id, Slack ts
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

-- Vector index added at Stage 1 once row counts and recall are known.
-- Likely HNSW: create index on chunk using hnsw (embedding vector_cosine_ops);
```

---

## Group 4: RAID (confirmed) vs risk findings (candidate, recommend-only)

This separation is what makes B3 real. The agent writes `risk_finding` rows. A human accepting one is what creates or links a `raid_entry`. Nothing auto-writes to the RAID log.

```sql
create table raid_entry (
  id                uuid primary key default gen_random_uuid(),
  type              raid_type not null,
  title             text not null,
  description       text not null,
  severity          severity_level,
  likelihood        severity_level,
  status            text,
  owner             text,
  team_id           uuid references team (id) on delete set null,
  source_artifact_id uuid references artifact (id) on delete set null,
  tenant_id         uuid not null,
  created_at        timestamptz not null default now()
);

create table risk_finding (
  id                uuid primary key default gen_random_uuid(),
  candidate_type    raid_type not null,
  description       text not null,
  severity_estimate severity_level,
  raid_entry_id     uuid references raid_entry (id) on delete set null,  -- set only on human accept
  status            finding_status not null default 'suggested',
  suggested_at      timestamptz not null default now(),
  decided_by        uuid references app_user (id) on delete set null,
  decided_at        timestamptz,
  tenant_id         uuid not null
);

-- Evidence as a join table (not a uuid[]) so each citation is a real, enforced FK.
create table risk_finding_evidence (
  finding_id  uuid not null references risk_finding (id) on delete cascade,
  chunk_id    uuid not null references chunk (id) on delete cascade,
  primary key (finding_id, chunk_id)
);
```

Design note: evidence is a join table rather than an array column so every "show your working" citation is a referential-integrity-enforced link to a real chunk. This is the provenance backbone for the risk agent.

---

## Group 5: Signals (the explainable watermelon)

Each signal stores its computed value **and** the reference threshold it was judged against, so the reasoning panel shows "burn ratio 0.31 vs reference 0.40" rather than a black-box verdict. Thresholds are transparent references, not hard gates (B2).

```sql
create table signal (
  id                  uuid primary key default gen_random_uuid(),
  team_id             uuid not null references team (id) on delete cascade,
  sprint_id           uuid references sprint (id) on delete cascade,
  signal_type         signal_type not null,
  computed_value      jsonb not null,        -- numeric or structured, depending on type
  reference_threshold text,                  -- the number/rule used, shown to the user
  reference_window    text,                  -- e.g. "2 sprints"
  breached            boolean not null default false,
  computed_at         timestamptz not null default now(),
  tenant_id           uuid not null
);
```

---

## Group 6: Outputs

Every report claim links to a chunk; the chunk carries `char_start` / `char_end`, so span-level citation is available later (D5).

```sql
create table report (
  id           uuid primary key default gen_random_uuid(),
  audience     audience not null,
  title        text not null,
  body         text not null,
  scope_type   report_scope not null,
  scope_id     uuid,                          -- team_id or sprint_id; null for portfolio
  model        text,
  generated_by uuid references app_user (id) on delete set null,
  generated_at timestamptz not null default now(),
  run_id       uuid not null,                 -- ties to the orchestration run in `event`
  tenant_id    uuid not null
);

create table report_citation (
  id           uuid primary key default gen_random_uuid(),
  report_id    uuid not null references report (id) on delete cascade,
  claim_anchor text not null,                 -- which claim in the body this supports
  chunk_id     uuid not null references chunk (id) on delete cascade,
  created_at   timestamptz not null default now()
);
```

---

## Group 7: Audit and reasoning log (unified)

One table does double duty. The reasoning panel reads `event` rows by `run_id`. The audit trail is the same data filtered differently. Per D3, `detail` holds references and a short rationale, never raw model payloads.

```sql
create table event (
  id          uuid primary key default gen_random_uuid(),
  occurred_at timestamptz not null default now(),
  actor_type  actor_type not null,
  actor_ref   text not null,                  -- user id or agent node name
  action      text not null,                  -- ingest | retrieve | compute_signal |
                                              -- suggest_risk | generate_report |
                                              -- accept_finding | login | role_change | ...
  target_type text,
  target_id   uuid,
  summary     text not null,
  detail      jsonb,                          -- references + short rationale only (D3)
  run_id      uuid,                           -- groups all steps of one orchestration run
  tenant_id   uuid not null
);

create index on event (run_id);
create index on event (occurred_at);
```

---

## Derived: the watermelon flag

The watermelon flag is computed, not stored, to avoid stale duplication. A team is a watermelon when it reports green or amber but has a breached red-implying signal in the window.

```sql
create view v_watermelon as
select
  s.id              as sprint_id,
  s.team_id,
  t.key             as team_key,
  s.reported_rag,
  count(sig.id) filter (where sig.breached) as breached_signals,
  (s.reported_rag in ('green', 'amber')
     and count(sig.id) filter (where sig.breached) > 0) as is_watermelon
from sprint s
join team t        on t.id = s.team_id
left join signal sig on sig.sprint_id = s.id
group by s.id, s.team_id, t.key, s.reported_rag;
```

This is a starting view. Stage 1 may refine which signal types count toward "red-implying" once the eval harness exists and the watermelon eval (SS-1.4) drives the exact rule.

---

## Provenance model (summary)

- **Ingest:** `artifact` records `source_type` + `source_ref` + `content_hash`. Nothing enters the corpus without a source.
- **Retrieve:** `chunk` belongs to an `artifact`. Retrieval returns chunks, each traceable to its artifact.
- **Reason:** `risk_finding_evidence` and `report_citation` link findings and report claims to specific chunks.
- **Record:** `event` logs every step by `run_id`, with references in `detail`.
- Net effect: any surfaced claim, risk, or watermelon flag can be walked back to source chunks and the run that produced it.

---

## Security posture (for the security review)

The three flags raised at draft are addressed by the locked decisions:

1. **Embedding egress (D1).** Resolved by choosing a self-hostable model run in-region. Chunk text does not leave the boundary to be embedded. If a hosted embedding provider is ever reconsidered, that is a new external-call decision and must be re-flagged.
2. **Reasoning-log contents (D3).** `event.detail` and the citation tables hold ids and short rationale, never raw prompt/response bodies. No second copy of client text outside ZDR scope.
3. **Encryption at rest.** Provided by managed Supabase UK/EU, locked in SS-1.8 (ADR-0002). Confirmed, no longer pending.

**Least privilege / least data:** roles are coarse (D4) and read-only by default (viewer). Writes that matter (accepting a risk finding) are human-gated and logged. `tenant_id` is present for future isolation but unenforced today (D2), which is acceptable only while single-tenant on synthetic data.

---

## Resolved dependency

- **SS-1.8 (auth + residency)** is locked: managed Supabase UK/EU (ADR-0002). This confirms the encryption-at-rest and identity assumptions above. If that ever changes (for example a gov self-host), revisit Group 1 and the security posture.

## Not in scope for v1 (no gold-plating)

- Multi-tenant RLS and policies.
- A roles/permissions table.
- Character-span citation rows (available later from `chunk` offsets).
- LLM-as-judge eval tables (Stage 4).
