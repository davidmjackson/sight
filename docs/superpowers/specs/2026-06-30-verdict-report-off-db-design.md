# Spec: Verdict and report off the live database (the "small job")

Date: 2026-06-30
Status: Approved (design), ready for implementation plan
Slice: real-wiring follow-on (rest of "Approach B")

## Plain-English summary (read this first)

Today Sight computes the watermelon verdict and the audience report from the local
sample files (the synthetic corpus), even when the live database is switched on. This
slice makes the verdict and report compute from documents loaded out of the live
Postgres (Supabase) instead, behind a new off-by-default switch, producing identical
results, with the detector's logic left completely unchanged.

This is the deliberately small version of "Approach B". We are NOT re-modelling delivery
data into structured tables, and we are NOT rewriting the detector. We are only changing
*where the detector's input documents come from*.

## Background: the finding that shaped this slice

The watermelon detector (`sprintsight/detector.py`) and the report writer
(`sprintsight/report/writer.py`) do not read structured numeric columns. They consume a
`dict[functional_id, Artifact]` and re-parse each artifact's raw markdown `body` with
regex for metrics (committed/completed/carry_over/velocity), reported RAG, RAID
risks/dependencies, and the chat-vs-RAID hidden-dependency signal.

Each `Artifact` they rely on carries: `artifact_id` (the functional id, e.g.
`status-atlas-s15`), `source_type`, `team`, `sprint` (int), and `body`. Verified: neither
the detector nor the report reads `Artifact.meta` or the native `source_ref`
(grep clean), so a faithful rebuild needs only the fields below.

The live DB (`db/migrations/0001_init.sql`) stores each artifact's `body`, `source_type`,
and `team_id`, but has **no column for the functional id and no sprint association**, so
the detector's input dict cannot currently be rebuilt from `artifact` rows. The structured
delivery-domain tables (`sprint_metric`, `burndown_snapshot`, `dependency`, `signal`)
exist but are empty and unread; the detector ignores them. Therefore the minimal,
lowest-risk path to "verdict off the DB" is to add the two missing tags and rebuild the
document bag, not to populate or read the structured tables.

## Goal and success criteria

Goal: behind `SPRINTSIGHT_VERDICT_DB=on`, the web app's verdict and report are computed
from artifacts loaded from Postgres, producing output identical to the corpus path.

Success criteria:
1. A new eval proves, for all five teams, that the verdict AND report computed from
   DB-sourced artifacts are identical to those computed from corpus-sourced artifacts,
   including Echo's "insufficient evidence" case.
2. The existing watermelon eval (4/4) and report eval stay green and untouched.
3. The detector (`detector.py`) and report writer (`writer.py`) are unchanged.
4. With the switch off (the default), CI, tests, and the current demo behave exactly as
   they do today. Any DB error with the switch on falls back to the corpus (fail-safe,
   never a 500).
5. CI stays fully offline (the parity test uses an in-memory store stand-in).

## Scope

In scope:
- Migration `0005`: two nullable columns on `artifact` (`functional_id`, `sprint`) + a
  partial-unique guard on `(tenant_id, functional_id)` where `functional_id is not null`.
- Persist `functional_id` and `sprint` at ingest (storage layer + both stores + pipeline),
  including folding them into the content-hash fingerprint so a re-ingest backfills them.
- A DB-backed artifact loader that rebuilds `dict[functional_id, Artifact]` for a team.
- Gated, fail-safe wiring of that loader into the web layer's artifact source.
- The new switch `SPRINTSIGHT_VERDICT_DB`.
- The parity eval + supporting tests.

Out of scope (deferred "big job"):
- Populating or reading the structured tables (`sprint_metric`, `burndown_snapshot`,
  `dependency`, `signal`).
- Rewriting the detector/report to read columns instead of parsing bodies.
- Persisting `Verdict`/`Report`/citations/RAID findings (Groups 4, 6, 7 unmigrated).

## Design

### 1. Schema: migration `0005_artifact_functional_tags.sql`

Add to `artifact`:
- `functional_id text` (nullable) — the detector key, e.g. `status-atlas-s15`.
- `sprint integer` (nullable) — the sprint number, e.g. 15.

Add a partial unique index `(tenant_id, functional_id) where functional_id is not null`
to document and enforce that a functional id is unique per tenant. Nullable so existing
rows and non-corpus rows are unaffected; backfilled by re-ingest.

### 2. Ingest: persist the two tags

`Store.upsert_artifact` gains `functional_id: str` and `sprint: int` parameters. Both
implementations are updated:
- `PostgresStore.upsert_artifact` writes the two new columns.
- The in-memory store carries them on its stored record.

`sprintsight/ingest/pipeline.py` passes `art.artifact_id` (the functional id) and
`art.sprint` through.

Dedup-hash fix (the recurring re-ingest trap): the content hash that ingest uses to skip
unchanged artifacts currently folds in the embedder signature. Fold `functional_id` and
`sprint` (or a bumped row-schema version token) into that same fingerprint, so the first
re-ingest after this change rewrites every row once and populates the new columns instead
of silently skipping on an unchanged body. Steady state afterwards.

### 3. The DB-backed artifact loader

A new function (proposed home: `sprintsight/retrieval/` or a small `db_corpus.py`) with a
signature mirroring the corpus loader, e.g. `db_artifacts_for(team: str, sprints) ->
dict[str, Artifact]`. It:
- Connects via the same lazy, tenant-scoped psycopg path as `PostgresRetriever`
  (sets `app.tenant_id`, filters `where a.tenant_id = %s`).
- Selects artifact rows for the team (join `team`, filter `t.key`/name) with
  `functional_id is not null` and `sprint = any(%s)`.
- Rebuilds `Artifact(artifact_id=functional_id, source_type=source_type, team=<team key>,
  sprint=sprint, meta={}, body=body)`. `meta={}` is safe (unused by detector/report).
- Is a pure-ish data fetch; no embedding needed (this path does not use vectors).

### 4. Web wiring + the switch

Add `_verdict_db_enabled()` to `sprintsight/web/service.py`, true only when
`SPRINTSIGHT_VERDICT_DB == "on"` AND `DATABASE_URL` is set (off by default).

Introduce one gated artifact source, e.g. `_artifacts_source(team)`, that returns
`db_artifacts_for(team, _SPRINTS)` when the gate is open, else `artifacts_for(team,
_SPRINTS)`. On any exception from the DB path, log and fall back to `artifacts_for`
(fail-safe). Route the existing call sites through it:
- `_verdict_or_none` (service.py:259)
- `team_detail` (service.py:237)
- the portfolio path that computes per-team verdicts (pin exact site in the plan)

Retrieval/loader stays a seam so tests can inject a fake (mirrors `_make_retriever`). The
detector (`graph_detector()`) and report writer are fed the artifacts dict and are
unchanged.

### 5. Eval-first proof

New test (proposed `tests/test_verdict_db_parity.py`): for each of the five teams, build
the artifacts dict both ways — from the corpus loader and from an in-memory DB stand-in
seeded with the same artifacts (including `functional_id` and `sprint`) — run the
unchanged detector and report on each, and assert the `Verdict` and `Report` are equal,
including Echo's `insufficient_evidence` path. Add a focused test that the ingest
re-write populates the two new columns (re-ingest backfill) and that the dedup hash now
folds them in. The existing watermelon (4/4) and report evals stay the CI gate and remain
untouched. CI stays offline.

## Risks and mitigations

- **Re-ingest backfill trap** (recurring): mitigated by folding the new fields into the
  content hash; covered by a re-ingest test. Documented as an operator step.
- **Hidden field dependency** breaking parity: mitigated by the grep proof that
  detector/report read only `functional_id`/`source_type`/`team`/`sprint`/`body`, and by
  the five-team parity eval (the real guard).
- **Accidental behaviour change with the switch off**: mitigated by off-by-default gating
  and the unchanged existing evals; CI never sets the flag.

## Operator step to go live (not part of CI)

After merge, to see it live: ensure migrations are applied (incl. `0005`), re-ingest the
live Supabase once to backfill `functional_id`/`sprint` (per the embedder runbook's
forced re-ingest), set `SPRINTSIGHT_VERDICT_DB=on` + `DATABASE_URL` (+ matching
`SPRINTSIGHT_EMBEDDER` and `SPRINTSIGHT_ENV=dev` for a local run), log in, open `/team/atlas`
and the portfolio. Until then the switch stays off and behaviour is unchanged.

## Learning queue flag (HANDOVER)

New concept for a non-engineer: "same logic, different data source behind a switch" —
the detector is unchanged; only where its input documents come from changes, proven by a
parity eval. Flag one line in the HANDOVER Learning queue at build time.
