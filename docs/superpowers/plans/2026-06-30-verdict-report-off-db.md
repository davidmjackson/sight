# Verdict and Report Off The Live DB — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Behind a new off-by-default switch, compute the watermelon verdict and the audience report from artifacts loaded out of Postgres instead of the local corpus files, producing identical output, with the detector and report writer unchanged.

**Architecture:** Add two nullable columns (`functional_id`, `sprint`) to the `artifact` table and persist them at ingest. A new `PostgresArtifactSource` rebuilds the `dict[functional_id, Artifact]` the detector expects from those rows. The web layer routes its two artifact-loading call sites through one gated, fail-safe source: DB when `SPRINTSIGHT_VERDICT_DB=on`, else the corpus. A five-team parity eval proves the DB-sourced verdict and report match the corpus path.

**Tech Stack:** Python 3.12, FastAPI (web), psycopg (Postgres/pgvector), pytest, ruff. The detector (`sprintsight/detector.py`) and report writer (`sprintsight/report/writer.py`) are NOT modified.

## Global Constraints

- Detector (`detector.py`) and report writer (`writer.py`) logic stays byte-for-byte unchanged. This slice only changes where input artifacts come from.
- New switch is fail-safe and off by default: `SPRINTSIGHT_VERDICT_DB == "on"` AND `DATABASE_URL` set. Any DB error with the switch on falls back to the corpus, never a 500.
- CI stays fully offline: no test requires a real database. The Postgres query path is exercised by the existing CI `db` job, not by unit tests.
- psycopg is imported lazily (inside functions), never at module top level, so modules import without the optional `db` extra.
- No em dashes in any doc text a human reads.
- New migration is `db/migrations/0005_artifact_functional_tags.sql` (0004 is the current highest). Columns are nullable; existing rows are unaffected.
- Tenant scoping mirrors the existing pattern: `set_config('app.tenant_id', <DEMO_TENANT_ID>, false)` per connection; every query filters `tenant_id = %s`.

---

### Task 1: Parity eval (eval-first guard)

This proves the core assumption before any plumbing: rebuilding an artifact from only the five stored fields (`functional_id`, `source_type`, `team`, `sprint`, `body`) with `meta={}` changes neither the verdict nor the report, for every team and audience. If this ever fails, the cheap-rebuild approach is invalid and the whole slice must stop.

**Files:**
- Test: `tests/test_verdict_db_parity.py` (create)

**Interfaces:**
- Consumes: `sprintsight.evals.fixtures.Artifact`, `artifacts_for`; `sprintsight.detector.detect`; `sprintsight.report.writer.compose`; `sprintsight.web.service.TEAMS`.
- Produces: a reusable test helper `db_shaped(arts)` (kept local to the test file) that simulates the DB round-trip.

- [ ] **Step 1: Write the parity test**

```python
"""Parity guard for the verdict-off-DB slice: rebuilding artifacts from only the columns the
DB stores (dropping `meta`) must not change the detector verdict or the composed report."""

import pytest

from sprintsight.detector import detect
from sprintsight.evals.fixtures import Artifact, artifacts_for
from sprintsight.report.writer import compose
from sprintsight.web.service import TEAMS

_SPRINTS = [14, 15]
_AUDIENCES = ("exec", "programme", "team")


def db_shaped(arts: dict[str, Artifact]) -> dict[str, Artifact]:
    """Simulate a DB round-trip: only the five persisted fields survive; `meta` is dropped.
    Mirrors exactly what PostgresArtifactSource rebuilds (Task 3)."""
    return {
        aid: Artifact(
            artifact_id=a.artifact_id,
            source_type=a.source_type,
            team=a.team,
            sprint=a.sprint,
            meta={},
            body=a.body,
        )
        for aid, a in arts.items()
    }


def _verdict_outcome(team, arts):
    """Capture the verdict OR the exception type, so teams with thin data (Echo) compare equal
    on both paths whatever detect() does."""
    try:
        return ("ok", detect({"team": team, "artifacts": arts}))
    except Exception as exc:  # noqa: BLE001 - we are comparing failure modes too
        return ("error", type(exc).__name__)


@pytest.mark.parametrize("team", TEAMS)
def test_verdict_parity(team):
    corpus = artifacts_for(team, _SPRINTS)
    rebuilt = db_shaped(corpus)
    assert _verdict_outcome(team, rebuilt) == _verdict_outcome(team, corpus)


@pytest.mark.parametrize("team", TEAMS)
@pytest.mark.parametrize("audience", _AUDIENCES)
def test_report_parity(team, audience):
    corpus = artifacts_for(team, _SPRINTS)
    rebuilt = db_shaped(corpus)
    got = compose({"team": team, "audience": audience, "artifacts": rebuilt})
    want = compose({"team": team, "audience": audience, "artifacts": corpus})
    assert got == want
```

- [ ] **Step 2: Run it (expected PASS, proving the assumption)**

Run: `pytest tests/test_verdict_db_parity.py -q`
Expected: PASS for all teams/audiences. (If `Verdict`/`Report` are not value-comparable, add `@dataclass(eq=True)` confirmation — they are frozen dataclasses, so `==` is by value. If a parity case FAILS, STOP: the rebuild approach is unsafe, escalate before continuing.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_verdict_db_parity.py
git commit -m "test: parity guard for verdict/report off DB (meta-drop rebuild) [SS-5]"
```

---

### Task 2: Persist functional_id + sprint at ingest

**Files:**
- Modify: `sprintsight/ingest/store.py` (ArtifactInput dataclass; `InMemoryStore.upsert_artifact`; `PostgresStore.upsert_artifact`)
- Modify: `sprintsight/ingest/pipeline.py` (`_content_hash`; the ingest loop)
- Modify: `db/migrations/0005_artifact_functional_tags.sql` (create)
- Test: `tests/test_ingest.py` (add cases; this file already exists)

**Interfaces:**
- Consumes: `Artifact.artifact_id` (the functional id), `Artifact.sprint`.
- Produces: `ArtifactInput.functional_id: str | None`, `ArtifactInput.sprint: int | None`; `_content_hash(body, embedder_sig, functional_id, sprint)`; `InMemoryStore` records now carry `functional_id`, `sprint`, `source_type`, `source_ref`.

- [ ] **Step 1: Write the migration**

Create `db/migrations/0005_artifact_functional_tags.sql`:

```sql
-- 0005: add the detector's functional id + sprint to artifact so the verdict and report can be
-- computed from DB-sourced artifacts (verdict-off-DB slice). Nullable: existing and non-corpus
-- rows are unaffected; backfilled by a re-ingest. Unique per tenant when present.
alter table artifact add column if not exists functional_id text;
alter table artifact add column if not exists sprint integer;

create unique index if not exists artifact_functional_id_uniq
  on artifact (tenant_id, functional_id)
  where functional_id is not null;
```

- [ ] **Step 2: Write the failing ingest test**

Add to `tests/test_ingest.py`:

```python
def test_ingest_persists_functional_id_and_sprint():
    from sprintsight.evals.fixtures import Artifact
    from sprintsight.ingest.embedding import HashingEmbedder
    from sprintsight.ingest.pipeline import ingest_corpus
    from sprintsight.ingest.store import InMemoryStore

    arts = {
        "status-atlas-s15": Artifact(
            artifact_id="status-atlas-s15", source_type="confluence", team="Atlas",
            sprint=15, meta={"source_ref": "ATLAS-STATUS-S15"}, body="Overall status: green",
        ),
    }
    store = InMemoryStore()
    ingest_corpus(store, HashingEmbedder(), artifacts=arts)

    row = store.artifact("confluence", "ATLAS-STATUS-S15")
    assert row is not None
    assert row["functional_id"] == "status-atlas-s15"
    assert row["sprint"] == 15


def test_reingest_backfills_after_hash_format_change():
    # A store populated under the OLD hash (body+embedder only) must NOT be skipped once the hash
    # folds in functional_id/sprint; it re-ingests so the new columns get populated.
    import hashlib

    from sprintsight.evals.fixtures import Artifact
    from sprintsight.ingest.embedding import HashingEmbedder, embedder_signature
    from sprintsight.ingest.pipeline import ingest_corpus
    from sprintsight.ingest.store import ArtifactInput, InMemoryStore

    art = Artifact(
        artifact_id="status-atlas-s15", source_type="confluence", team="Atlas", sprint=15,
        meta={"source_ref": "ATLAS-STATUS-S15"}, body="Overall status: green",
    )
    sig = embedder_signature(HashingEmbedder())
    old_hash = hashlib.sha256(f"{sig}\n{art.body}".encode()).hexdigest()  # OLD format
    store = InMemoryStore()
    store.upsert_team("Atlas", "Atlas")
    store.upsert_artifact(ArtifactInput(
        source_type="confluence", source_ref="ATLAS-STATUS-S15", title=None, body=art.body,
        author=None, source_timestamp=None, content_hash=old_hash, team_id="t1",
    ))

    report = ingest_corpus(store, HashingEmbedder(), artifacts={art.artifact_id: art})
    assert report.ingested == 1  # NOT skipped
    assert store.artifact("confluence", "ATLAS-STATUS-S15")["functional_id"] == "status-atlas-s15"
```

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/test_ingest.py::test_ingest_persists_functional_id_and_sprint tests/test_ingest.py::test_reingest_backfills_after_hash_format_change -v`
Expected: FAIL (`ArtifactInput` has no `functional_id`; `row["functional_id"]` KeyError).

- [ ] **Step 4: Extend ArtifactInput**

In `sprintsight/ingest/store.py`, add two fields to the dataclass:

```python
@dataclass(frozen=True)
class ArtifactInput:
    source_type: str
    source_ref: str
    title: str | None
    body: str
    author: str | None
    source_timestamp: str | None
    content_hash: str
    team_id: str | None = None
    functional_id: str | None = None
    sprint: int | None = None
```

- [ ] **Step 5: Store the new fields in InMemoryStore**

Replace `InMemoryStore.upsert_artifact` body's stored dict so it keeps the new fields and the lookup keys (used by the parity/loader tests):

```python
    def upsert_artifact(self, art: ArtifactInput) -> str:
        key = (art.source_type, art.source_ref)
        existing = self._artifacts.get(key)
        artifact_id = existing["id"] if existing else self._next_id()
        self._artifacts[key] = {
            "id": artifact_id,
            "content_hash": art.content_hash,
            "title": art.title,
            "body": art.body,
            "team_id": art.team_id,
            "source_type": art.source_type,
            "source_ref": art.source_ref,
            "functional_id": art.functional_id,
            "sprint": art.sprint,
        }
        return artifact_id
```

- [ ] **Step 6: Write the new columns in PostgresStore**

In `PostgresStore.upsert_artifact`, extend the insert column list, the values placeholders, the on-conflict update, and the params tuple:

```python
    def upsert_artifact(self, art: ArtifactInput) -> str:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                insert into artifact
                  (source_type, source_ref, title, body, author, source_timestamp,
                   content_hash, team_id, functional_id, sprint, tenant_id)
                values (%s::source_type, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s, %s, %s)
                on conflict (tenant_id, source_type, source_ref) do update set
                  title = excluded.title,
                  body = excluded.body,
                  author = excluded.author,
                  source_timestamp = excluded.source_timestamp,
                  content_hash = excluded.content_hash,
                  team_id = excluded.team_id,
                  functional_id = excluded.functional_id,
                  sprint = excluded.sprint,
                  ingested_at = now()
                returning id
                """,
                (
                    art.source_type,
                    art.source_ref,
                    art.title,
                    art.body,
                    art.author,
                    art.source_timestamp,
                    art.content_hash,
                    art.team_id,
                    art.functional_id,
                    art.sprint,
                    self.tenant_id,
                ),
            )
            return str(cur.fetchone()[0])
```

- [ ] **Step 7: Fold the new fields into the content hash and pass them through**

In `sprintsight/ingest/pipeline.py`, update `_content_hash` and the loop:

```python
def _content_hash(body: str, embedder_sig: str, functional_id: str, sprint: int) -> str:
    # functional_id + sprint are part of the key so the FIRST re-ingest after they became
    # persisted re-writes every row (and backfills the new columns) instead of skipping on an
    # unchanged body. The embedder signature keeps stored vectors valid for their embedder.
    return hashlib.sha256(
        f"{embedder_sig}\n{functional_id}\n{sprint}\n{body}".encode()
    ).hexdigest()
```

In the loop, change the hash call and the `ArtifactInput`:

```python
        content_hash = _content_hash(art.body, embedder_sig, art.artifact_id, art.sprint)

        if store.get_content_hash(source_type, source_ref) == content_hash:
            report.skipped += 1
            continue

        artifact_id = store.upsert_artifact(
            ArtifactInput(
                source_type=source_type,
                source_ref=source_ref,
                title=art.meta.get("title"),
                body=art.body,
                author=art.meta.get("author"),
                source_timestamp=art.meta.get("source_timestamp"),
                content_hash=content_hash,
                team_id=team_ids[art.team],
                functional_id=art.artifact_id,
                sprint=art.sprint,
            )
        )
```

- [ ] **Step 8: Update any direct `_content_hash` callers in tests**

Run: `grep -rn "_content_hash" tests/`
For each hit, update the call to the new 4-arg signature (add the artifact's `artifact_id` and `sprint`). If none, skip.

- [ ] **Step 9: Run the ingest tests**

Run: `pytest tests/test_ingest.py -v`
Expected: PASS (including the two new tests).

- [ ] **Step 10: Commit**

```bash
git add db/migrations/0005_artifact_functional_tags.sql sprintsight/ingest/store.py sprintsight/ingest/pipeline.py tests/test_ingest.py
git commit -m "feat(ingest): persist functional_id + sprint; fold into dedup hash; migration 0005 [SS-5]"
```

---

### Task 3: DB-backed artifact source

**Files:**
- Create: `sprintsight/retrieval/db_corpus.py`
- Test: `tests/retrieval/test_db_corpus.py` (create; create `tests/retrieval/__init__.py` if the dir is new)

**Interfaces:**
- Consumes: `sprintsight.evals.fixtures.Artifact`; `sprintsight.ingest.store.DEMO_TENANT_ID`.
- Produces: `rows_to_artifacts(rows) -> dict[str, Artifact]` (pure, unit-tested offline) and `PostgresArtifactSource(dsn, tenant_id=...)` with `.artifacts_for(team, sprints=None) -> dict[str, Artifact]` and `.close()`.

- [ ] **Step 1: Write the failing test for the pure mapping**

```python
from sprintsight.retrieval.db_corpus import rows_to_artifacts


def test_rows_to_artifacts_rebuilds_keyed_dict():
    rows = [
        ("status-atlas-s15", "confluence", "Atlas", 15, "Overall status: green"),
        ("burndown-atlas-s15", "jira", "Atlas", 15, "committed 40 completed 30"),
    ]
    arts = rows_to_artifacts(rows)
    assert set(arts) == {"status-atlas-s15", "burndown-atlas-s15"}
    a = arts["status-atlas-s15"]
    assert a.artifact_id == "status-atlas-s15"
    assert a.source_type == "confluence"
    assert a.team == "Atlas"
    assert a.sprint == 15
    assert a.body == "Overall status: green"
    assert a.meta == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/retrieval/test_db_corpus.py -v`
Expected: FAIL (module `db_corpus` does not exist).

- [ ] **Step 3: Implement `db_corpus.py`**

```python
"""Load corpus artifacts back out of Postgres for the verdict/report (verdict-off-DB slice).

Rebuilds the dict[functional_id, Artifact] the detector expects from `artifact` rows, using the
functional_id + sprint columns (migration 0005). psycopg is lazy. Tenant-scoped like
PostgresRetriever. This path reads whole bodies, not chunks, so it needs no embeddings.
"""

from collections.abc import Sequence

from sprintsight.evals.fixtures import Artifact
from sprintsight.ingest.store import DEMO_TENANT_ID

# Each row: (functional_id, source_type, team_key, sprint, body)
Row = Sequence[object]


def rows_to_artifacts(rows: list[Row]) -> dict[str, Artifact]:
    """Pure: map DB rows to the keyed Artifact dict. `meta` is empty by design (the detector and
    report never read it; verified by the parity eval)."""
    out: dict[str, Artifact] = {}
    for functional_id, source_type, team_key, sprint, body in rows:
        fid = str(functional_id)
        out[fid] = Artifact(
            artifact_id=fid,
            source_type=str(source_type),
            team=str(team_key),
            sprint=int(sprint),
            meta={},
            body=str(body),
        )
    return out


class PostgresArtifactSource:
    """Reads artifacts for a team out of Postgres, keyed by functional_id (production path)."""

    def __init__(self, dsn: str, tenant_id: str = DEMO_TENANT_ID) -> None:
        import psycopg  # lazy: only when querying a real DB

        self.tenant_id = tenant_id
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._conn.execute("select set_config('app.tenant_id', %s, false)", (tenant_id,))

    def artifacts_for(
        self, team: str, sprints: list[int] | None = None
    ) -> dict[str, Artifact]:
        conditions = ["a.tenant_id = %s", "a.functional_id is not null", "lower(t.key) = lower(%s)"]
        params: list[object] = [self.tenant_id, team]
        if sprints is not None:
            conditions.append("a.sprint = any(%s)")
            params.append(list(sprints))
        where = "where " + " and ".join(conditions)
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                select a.functional_id, a.source_type::text, coalesce(t.key, '') as team,
                       a.sprint, a.body
                from artifact a
                left join team t on t.id = a.team_id
                {where}
                """,
                tuple(params),
            )
            rows = cur.fetchall()
        return rows_to_artifacts(rows)

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/retrieval/test_db_corpus.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sprintsight/retrieval/db_corpus.py tests/retrieval/test_db_corpus.py
git commit -m "feat(retrieval): PostgresArtifactSource rebuilds team artifacts from DB rows [SS-5]"
```

---

### Task 4: Gated, fail-safe web wiring

**Files:**
- Modify: `sprintsight/web/service.py` (add gate + seam + `_artifacts_for`; route `:237` and `:259`)
- Test: `tests/web/test_verdict_db.py` (create)

**Interfaces:**
- Consumes: `PostgresArtifactSource` (Task 3); `artifacts_for` (corpus fallback).
- Produces: `_verdict_db_enabled() -> bool`; `_make_artifact_source()` (seam tests monkeypatch); `_artifacts_for(team) -> dict[str, Artifact]`.

- [ ] **Step 1: Write the failing web test**

```python
"""Gating + fail-safe wiring for verdict/report off the DB."""

import sprintsight.web.service as svc
from sprintsight.evals.fixtures import Artifact


class _FakeSource:
    def __init__(self, arts):
        self._arts = arts
        self.closed = False

    def artifacts_for(self, team, sprints=None):
        return self._arts

    def close(self):
        self.closed = True


def _one_atlas_artifact():
    return {
        "status-atlas-s15": Artifact(
            artifact_id="status-atlas-s15", source_type="confluence", team="Atlas",
            sprint=15, meta={}, body="Overall status: green",
        )
    }


def test_gate_off_uses_corpus(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_VERDICT_DB", raising=False)
    arts = svc._artifacts_for("Atlas")
    # corpus has the real multi-artifact set, not our single fake
    assert "burndown-atlas-s15" in arts


def test_gate_on_uses_db_source(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_VERDICT_DB", "on")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    fake = _FakeSource(_one_atlas_artifact())
    monkeypatch.setattr(svc, "_make_artifact_source", lambda: fake)
    arts = svc._artifacts_for("Atlas")
    assert set(arts) == {"status-atlas-s15"}
    assert fake.closed is True


def test_db_error_falls_back_to_corpus(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_VERDICT_DB", "on")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(svc, "_make_artifact_source", _boom)
    arts = svc._artifacts_for("Atlas")
    assert "burndown-atlas-s15" in arts  # corpus fallback


def test_empty_db_falls_back_to_corpus(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_VERDICT_DB", "on")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setattr(svc, "_make_artifact_source", lambda: _FakeSource({}))
    arts = svc._artifacts_for("Atlas")
    assert "burndown-atlas-s15" in arts  # un-backfilled DB -> corpus
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/web/test_verdict_db.py -v`
Expected: FAIL (`svc._artifacts_for` does not exist).

- [ ] **Step 3: Add the gate, seam, and source function**

In `sprintsight/web/service.py`, after the existing `_db_enabled()` / `_make_retriever()` block (around line 87), add:

```python
# --- DB-backed verdict/report source (verdict-off-DB slice), fail-safe and off by default ---
_VERDICT_DB_FLAG = "SPRINTSIGHT_VERDICT_DB"


def _verdict_db_enabled() -> bool:
    """True only when the verdict-DB switch is deliberately on AND a DATABASE_URL is set."""
    return os.environ.get(_VERDICT_DB_FLAG) == "on" and bool(os.environ.get("DATABASE_URL"))


def _make_artifact_source():
    """Build the production artifact source. Seam: tests inject a fake; psycopg stays lazy."""
    from sprintsight.retrieval.db_corpus import PostgresArtifactSource

    return PostgresArtifactSource(os.environ["DATABASE_URL"])


def _artifacts_for(team: str) -> dict[str, Artifact]:
    """Team artifacts for the verdict and report. DB when the verdict-DB gate is open, else the
    corpus. Fail-safe: any DB error, or an empty (un-backfilled) result, falls back to the corpus
    so the app never blanks out or 500s on a DB problem."""
    if not _verdict_db_enabled():
        return artifacts_for(team, _SPRINTS)
    source = None
    try:
        source = _make_artifact_source()
        arts = source.artifacts_for(team, _SPRINTS)
        return arts if arts else artifacts_for(team, _SPRINTS)
    except Exception:
        logging.exception("DB artifact source failed for team %s; using corpus", team)
        return artifacts_for(team, _SPRINTS)
    finally:
        if source is not None:
            source.close()
```

- [ ] **Step 4: Route the two call sites through the gated source**

In `team_detail` (currently `service.py:237`) replace:

```python
    arts = artifacts_for(team, _SPRINTS)
```
with:
```python
    arts = _artifacts_for(team)
```

In `_verdict_or_none` (currently `service.py:259`) replace:

```python
    arts = artifacts_for(team, _SPRINTS)
```
with:
```python
    arts = _artifacts_for(team)
```

(The portfolio path calls `_verdict_or_none`, so it picks up the DB source automatically. Leave the direct `artifacts_for` import in place; it is still used as the fallback.)

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/web/test_verdict_db.py -v`
Expected: PASS (all four cases).

- [ ] **Step 6: Commit**

```bash
git add sprintsight/web/service.py tests/web/test_verdict_db.py
git commit -m "feat(web): verdict/report off DB behind SPRINTSIGHT_VERDICT_DB, fail-safe [SS-5]"
```

---

### Task 5: CI db-job assertion + docs + learning flag

**Files:**
- Create: `db/checks/functional_id_present.sql`
- Modify: the CI workflow `db` job (read `.github/workflows/*.yml`; mirror the existing `team_id` / null-check step)
- Create/Modify: `docs/db/verdict-off-db.md` (operator runbook note)
- Modify: `HANDOVER.md` (Learning queue: one line)

**Interfaces:** none (infra + docs).

- [ ] **Step 1: Add the db-job assertion SQL**

Create `db/checks/functional_id_present.sql` (mirrors the existing team_id null-check intent: after ingest, every corpus artifact must carry a functional id):

```sql
-- After ingest, every artifact must have a functional_id (verdict-off-DB slice).
-- Exits non-zero via the harness when the count is wrong; see the CI db job.
select
  count(*) filter (where functional_id is null) as null_functional_id,
  count(*) filter (where sprint is null)        as null_sprint
from artifact;
```

- [ ] **Step 2: Wire it into the CI db job**

Open the workflow that runs the `db` job (`grep -rn "rls_isolation\|retrieve_smoke\|team_id" .github/workflows/`). After the ingest step, add a step that runs `db/checks/functional_id_present.sql` and fails if `null_functional_id` is not 0 (mirror the assertion style already used for the team_id / 5-teams check — reuse the same psql + grep/`-v ON_ERROR_STOP=1` pattern that step uses). Keep it offline-DB only (the CI pgvector service), not a real Supabase.

- [ ] **Step 3: Write the operator runbook note**

Create `docs/db/verdict-off-db.md`:

```markdown
# Verdict and report off the live database

Plain summary: a switch that makes the web app compute the watermelon verdict and the report
from the live database instead of the local sample files. Off by default.

## What it needs
1. Migrations applied through `0005_artifact_functional_tags.sql`.
2. A one-time re-ingest of the live database so the new `functional_id` and `sprint` columns
   get filled in (the ingest dedup hash now folds these in, so the first re-ingest rewrites
   every row once; steady state afterwards).
3. Environment: `SPRINTSIGHT_VERDICT_DB=on`, `DATABASE_URL=<session pooler url>`, and the same
   `SPRINTSIGHT_EMBEDDER` you ingested with. For a local run also set `SPRINTSIGHT_ENV=dev`.

## Verify
Log in, open `/team/atlas` and the portfolio. The verdict and report now come from the database.
If the database is unreachable or not yet backfilled, the app silently falls back to the sample
files (fail-safe), so a misconfiguration never 500s; it just looks like today's behaviour.

## Switch off
Unset `SPRINTSIGHT_VERDICT_DB` (or set it to anything other than `on`). Behaviour returns to the
sample files immediately.
```

- [ ] **Step 4: Flag the learning queue (one line, do NOT edit LEARNING-LOG.md)**

Append one line to the `Learning queue` section of `HANDOVER.md`:

```
- Same logic, different data source behind a switch | the detector is unchanged; only where its input documents come from changes (corpus vs live DB), proven by a parity eval | verdict-off-db slice (SPRINTSIGHT_VERDICT_DB) | 2026-06-30
```

- [ ] **Step 5: Commit**

```bash
git add db/checks/functional_id_present.sql docs/db/verdict-off-db.md HANDOVER.md .github/workflows/
git commit -m "ci+docs: assert functional_id populated; verdict-off-DB runbook + learning flag [SS-5]"
```

---

### Task 6: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the whole suite + linter**

Run: `pytest -q && ruff check sprintsight tests`
Expected: all pass (target ~313 + the new tests), ruff clean.

- [ ] **Step 2: Confirm the eval gates are unchanged**

Run: `pytest tests/ -q -k "watermelon or report or crosstool"`
Expected: deterministic eval gates still green (watermelon 4/4, report 4/4, cross-tool 7/7).

- [ ] **Step 3: Confirm the switch is off by default (no behaviour change)**

Run: `python -c "import sprintsight.web.service as s; print(s._verdict_db_enabled())"`
Expected: `False`.

---

## Self-Review

**Spec coverage:**
- Migration 0005 (two nullable columns + partial unique index) → Task 2 Step 1. ✓
- Persist functional_id/sprint at ingest + dedup-hash fold → Task 2. ✓
- DB-backed loader rebuilding the keyed Artifact dict → Task 3. ✓
- Gated, fail-safe web wiring + new switch → Task 4. ✓
- Five-team parity proof (incl. Echo) for verdict AND report → Task 1 (verdict + report parametrized over teams/audiences). ✓
- Existing evals stay green; detector/report unchanged → Task 6 Step 2 + Global Constraints. ✓
- CI stays offline; Postgres path via CI db job → Task 5 Step 2 + Global Constraints. ✓
- Operator re-ingest step documented → Task 5 Step 3. ✓
- Learning-queue flag (not LEARNING-LOG) → Task 5 Step 4. ✓

**Placeholder scan:** Task 5 Step 2 intentionally defers exact CI workflow line edits to "read the workflow and mirror the existing team_id check" because the workflow file's structure must be read at implementation time; the pattern to copy is named explicitly. All code steps contain complete code.

**Type consistency:** `functional_id`/`sprint` are `str | None`/`int | None` on `ArtifactInput`; `_content_hash(body, embedder_sig, functional_id, sprint)` 4-arg everywhere; `rows_to_artifacts(rows)` and `PostgresArtifactSource.artifacts_for(team, sprints=None)` returns match `_artifacts_for`'s consumption; `_make_artifact_source` is the monkeypatch seam used in Task 4 tests. Consistent.
