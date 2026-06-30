-- 0005: add the detector's functional id + sprint to artifact so the verdict and report can be
-- computed from DB-sourced artifacts (verdict-off-DB slice). Nullable: existing and non-corpus
-- rows are unaffected; backfilled by a re-ingest. Unique per tenant when present.
alter table artifact add column if not exists functional_id text;
alter table artifact add column if not exists sprint integer;

create unique index if not exists artifact_functional_id_uniq
  on artifact (tenant_id, functional_id)
  where functional_id is not null;
