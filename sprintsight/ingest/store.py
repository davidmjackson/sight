"""Artifact/chunk stores: an in-memory store for tests and a Postgres+pgvector store.

Both implement the `Store` protocol the pipeline depends on, so ingestion is identical
whether it targets a fake or a real database. Idempotency is keyed on `content_hash`:
re-ingesting an unchanged artifact is a no-op; a changed one replaces its chunks.

Single-tenant for the showcase: `tenant_id` is a fixed constant (decision D2, unenforced).
"""

from dataclasses import dataclass, field
from typing import Protocol

from sprintsight.ingest.embedding import to_pgvector

# Fixed demo tenant — single-tenant showcase (schema decision D2).
DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"


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


# (Chunk, embedding) pairs to write for an artifact.
EmbeddedChunk = tuple[object, list[float]]


class Store(Protocol):
    def upsert_team(self, key: str, name: str) -> str: ...
    def get_content_hash(self, source_type: str, source_ref: str) -> str | None: ...
    def upsert_artifact(self, art: ArtifactInput) -> str: ...
    def replace_chunks(self, artifact_id: str, chunks: list[EmbeddedChunk]) -> int: ...
    def counts(self) -> dict[str, int]: ...
    def close(self) -> None: ...


@dataclass
class InMemoryStore:
    """Dict-backed store for tests and offline runs."""

    tenant_id: str = DEMO_TENANT_ID
    _artifacts: dict[tuple[str, str], dict] = field(default_factory=dict)
    _chunks: dict[str, list[dict]] = field(default_factory=dict)
    _teams: dict[str, str] = field(default_factory=dict)  # team key -> team id
    _seq: int = 0

    def upsert_team(self, key: str, name: str) -> str:
        if key not in self._teams:
            self._teams[key] = self._next_id()
        return self._teams[key]

    def get_content_hash(self, source_type: str, source_ref: str) -> str | None:
        row = self._artifacts.get((source_type, source_ref))
        return row["content_hash"] if row else None

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

    # --- read accessors (used by tests / offline inspection) ---
    def team_keys(self) -> list[str]:
        return list(self._teams)

    def team_index(self) -> dict[str, str]:
        return dict(self._teams)

    def artifacts(self):
        return list(self._artifacts.values())

    def artifact(self, source_type: str, source_ref: str) -> dict | None:
        return self._artifacts.get((source_type, source_ref))

    def replace_chunks(self, artifact_id: str, chunks: list[EmbeddedChunk]) -> int:
        self._chunks[artifact_id] = [
            {
                "ordinal": c.ordinal,
                "text": c.text,
                "char_start": c.char_start,
                "char_end": c.char_end,
                "embedding": emb,
            }
            for c, emb in chunks
        ]
        return len(chunks)

    def counts(self) -> dict[str, int]:
        return {
            "team": len(self._teams),
            "artifact": len(self._artifacts),
            "chunk": sum(len(v) for v in self._chunks.values()),
        }

    def close(self) -> None:
        pass

    def _next_id(self) -> str:
        self._seq += 1
        return f"mem-{self._seq:04d}"


class PostgresStore:
    """Postgres + pgvector store (psycopg). Used in CI against the migration's service DB
    and in deployment against Supabase. psycopg is imported lazily so the module imports
    without the optional `db` extra installed."""

    def __init__(self, dsn: str, tenant_id: str = DEMO_TENANT_ID) -> None:
        import psycopg  # lazy: only needed when actually talking to Postgres

        self.tenant_id = tenant_id
        self._conn = psycopg.connect(dsn, autocommit=True)
        # Announce this connection's tenant so per-tenant RLS policies (migration 0003) scope every
        # query/insert at the DB. session-level (local=false) is correct under autocommit.
        self._conn.execute("select set_config('app.tenant_id', %s, false)", (tenant_id,))

    def upsert_team(self, key: str, name: str) -> str:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                insert into team (key, name, tenant_id)
                values (%s, %s, %s)
                on conflict (tenant_id, key) do update set name = excluded.name
                returning id
                """,
                (key, name, self.tenant_id),
            )
            return str(cur.fetchone()[0])

    def get_content_hash(self, source_type: str, source_ref: str) -> str | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "select content_hash from artifact "
                "where tenant_id = %s and source_type = %s and source_ref = %s",
                (self.tenant_id, source_type, source_ref),
            )
            row = cur.fetchone()
            return row[0] if row else None

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

    def replace_chunks(self, artifact_id: str, chunks: list[EmbeddedChunk]) -> int:
        with self._conn.cursor() as cur:
            cur.execute("delete from chunk where artifact_id = %s", (artifact_id,))
            for c, emb in chunks:
                cur.execute(
                    """
                    insert into chunk
                      (artifact_id, ordinal, text, char_start, char_end, embedding, tenant_id)
                    values (%s, %s, %s, %s, %s, %s::vector, %s)
                    """,
                    (
                        artifact_id,
                        c.ordinal,
                        c.text,
                        c.char_start,
                        c.char_end,
                        to_pgvector(emb),
                        self.tenant_id,
                    ),
                )
        return len(chunks)

    def counts(self) -> dict[str, int]:
        with self._conn.cursor() as cur:
            cur.execute("select count(*) from team")
            teams = cur.fetchone()[0]
            cur.execute("select count(*) from artifact")
            artifacts = cur.fetchone()[0]
            cur.execute("select count(*) from chunk")
            chunks = cur.fetchone()[0]
        return {"team": teams, "artifact": artifacts, "chunk": chunks}

    def close(self) -> None:
        self._conn.close()
