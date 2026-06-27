# Plan: Populate artifact.team_id (real-wiring slice 3)

Date: 2026-06-27
Spec: docs/superpowers/specs/2026-06-27-populate-team-id-design.md
Build style: eval-first (pytest in-memory gate written first), independent whole-branch review
before merge.

## Files

New:
- `tests/test_team_id.py` — the team_id population eval (write FIRST).

Edit:
- `sprintsight/ingest/store.py` — `Store.upsert_team`; `ArtifactInput.team_id`; both stores set
  team_id; `counts()` adds `team`.
- `sprintsight/ingest/pipeline.py` — resolve distinct teams via `upsert_team`, pass `team_id`.
- `sprintsight/retrieval/postgres.py` — optional `team` filter + return team key; update docstring.
- `.github/workflows/ci.yml` — extend the `db` verify step (team rows + non-null team_id) + a
  team-scoped retrieval assertion.
- `docs/embedder/real-embedder.md` (or a short team note) — document the live backfill-via-reingest.

Untouched: schema (team/artifact tables already have the columns), the in-memory retriever (already
team-scopes off the corpus), the web/detector (slice 4).

## Steps (in order)

1. **Eval-first, RED.** `tests/test_team_id.py`:
   - `ingest_corpus(InMemoryStore(), HashingEmbedder())`; assert `store.counts()["team"] == 5`;
     assert every artifact row has a non-None `team_id`; pick one known artifact and assert its
     `team_id` maps (via the store's team table) back to the right team key.
   - Run; it fails (no `upsert_team`, no team_id stored, no `team` count).

2. **Store changes** (`store.py`):
   - `ArtifactInput`: add `team_id: str | None = None` (defaulted → back-compatible).
   - `Store` protocol: add `upsert_team(self, key: str, name: str) -> str`.
   - `InMemoryStore`: add `_teams: dict[str, str]` (key→id); `upsert_team` returns existing or a new
     id; store `team_id` in the artifact row; `counts()` adds `"team": len(self._teams)`.
   - `PostgresStore`: `upsert_team` does `insert ... on conflict (tenant_id, key) do update set name=excluded.name returning id`;
     `upsert_artifact` adds `team_id` to the column list, values, and the on-conflict update set;
     `counts()` adds `team` from `select count(*) from team`.

3. **Pipeline** (`pipeline.py`): before the loop, `team_ids = {t: store.upsert_team(t, t) for t in
   sorted({a.team for a in artifacts.values()})}`; in the loop pass `team_id=team_ids[art.team]` into
   `ArtifactInput`. (Teams are upserted up front so they exist even when every artifact skips.)
   - Re-run step-1 test → GREEN.

4. **PostgresRetriever** (`postgres.py`): add `team: str | None = None`; left-join `team t on t.id =
   a.team_id`, `select t.key`; when `team` is set, `where t.key = %s` (+ tenant scope via
   `DEMO_TENANT_ID`); populate `RetrievedChunk.team` from `t.key`. Update the docstring (scoping now
   supported). No pytest (DB path); proven in CI `db` job.

5. **CI `db` job** (`ci.yml`): in the verify block add `team` count == 5 and
   `count(*) from artifact where team_id is null` == 0; add a small team-scoped retrieval assertion
   (extend `retrieve_smoke.py` with an optional team arg, or a psql check that a team-scoped select
   returns only that team).

6. **Gate:** `ruff` clean; full `pytest` green (new test passes, idempotency + embedder tests still
   pass — `counts()` gains `team` on both sides so the equality assertion holds); deterministic eval
   gates unchanged.

7. **Runbook note**: document that an already-populated DB backfills `team_id` on the next full
   re-ingest (which the slice-2 real-embedder switch already triggers).

8. **Independent whole-branch review** (separate agent) before merge. Apply blocking findings.

9. **Merge** `--no-ff`; update HANDOVER + memory + Learning-queue flag; push.

## Risk / mitigation

- Already-populated DB keeps NULL team_id on a no-op re-ingest -> documented; rides the slice-2
  re-embed; fresh DBs always get it.
- `counts()` shape change breaking the idempotency equality test -> both sides gain `team`, equality
  holds; verified by running the suite.
- Adding team_id to upsert_artifact conflict-update -> keep it in the update set so a changed artifact
  refreshes its link too.
