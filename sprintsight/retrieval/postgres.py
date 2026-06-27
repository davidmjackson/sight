"""Postgres + pgvector retriever (production path).

Cosine-distance search over `chunk`, joined to `artifact` (provenance) and left-joined to `team`
(team key). psycopg is imported lazily so this module loads without the optional `db` extra.
Team scoping is supported now that `artifact.team_id` is populated (real-wiring slice 3): pass
`team` to restrict the search to one team; omit it for a global search.
"""

from sprintsight.ingest.embedding import Embedder
from sprintsight.ingest.store import DEMO_TENANT_ID
from sprintsight.retrieval.retriever import RetrievedChunk


class PostgresRetriever:
    def __init__(self, dsn: str, tenant_id: str = DEMO_TENANT_ID) -> None:
        import psycopg  # lazy: only when querying a real DB

        self.tenant_id = tenant_id
        self._conn = psycopg.connect(dsn, autocommit=True)
        # Announce this connection's tenant so per-tenant RLS policies (migration 0003) scope every
        # query at the DB. session-level (local=false) is correct under autocommit.
        self._conn.execute("select set_config('app.tenant_id', %s, false)", (tenant_id,))

    def search(
        self,
        query: str,
        embedder: Embedder,
        k: int = 5,
        team: str | None = None,
    ) -> list[RetrievedChunk]:
        emb = embedder.embed([query])[0]
        vec = "[" + ",".join(repr(x) for x in emb) + "]"
        # Always tenant-scoped (single-tenant today; one less edit when RLS/multi-tenant lands).
        params: list[object] = [vec, self.tenant_id]
        conditions = ["a.tenant_id = %s"]
        if team is not None:
            # Scope to one team by key. team_id is populated at ingest (slice 3).
            conditions.append("t.key = %s")
            params.append(team)
        where = "where " + " and ".join(conditions)
        params += [vec, k]
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                select a.source_type, a.source_ref, coalesce(t.key, '') as team,
                       c.ordinal, c.text, (c.embedding <=> %s::vector) as distance
                from chunk c
                join artifact a on a.id = c.artifact_id
                left join team t on t.id = a.team_id
                {where}
                order by c.embedding <=> %s::vector
                limit %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()

        return [
            RetrievedChunk(
                artifact_id="",  # not persisted in the DB yet; source_ref is the DB provenance
                source_type=str(source_type),
                source_ref=source_ref,
                team=team_key,
                sprint=0,
                ordinal=ordinal,
                text=text,
                score=max(0.0, 1.0 - float(distance)),  # cosine distance -> similarity (clamped)
            )
            for source_type, source_ref, team_key, ordinal, text, distance in rows
        ]

    def close(self) -> None:
        self._conn.close()
