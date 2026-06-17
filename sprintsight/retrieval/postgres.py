"""Postgres + pgvector retriever (production path).

Cosine-distance search over `chunk`, joined to `artifact` for provenance. psycopg is
imported lazily so this module loads without the optional `db` extra. Team scoping awaits
`artifact.team_id` population (a delivery-domain loading step); global search is supported now.
"""

from sprintsight.ingest.embedding import Embedder
from sprintsight.retrieval.retriever import RetrievedChunk


class PostgresRetriever:
    def __init__(self, dsn: str) -> None:
        import psycopg  # lazy: only when querying a real DB

        self._conn = psycopg.connect(dsn, autocommit=True)

    def search(
        self,
        query: str,
        embedder: Embedder,
        k: int = 5,
    ) -> list[RetrievedChunk]:
        emb = embedder.embed([query])[0]
        vec = "[" + ",".join(repr(x) for x in emb) + "]"
        with self._conn.cursor() as cur:
            cur.execute(
                """
                select a.source_type, a.source_ref, c.ordinal, c.text,
                       (c.embedding <=> %s::vector) as distance
                from chunk c
                join artifact a on a.id = c.artifact_id
                order by c.embedding <=> %s::vector
                limit %s
                """,
                (vec, vec, k),
            )
            rows = cur.fetchall()

        return [
            RetrievedChunk(
                artifact_id="",  # not persisted in the DB yet; source_ref is the DB provenance
                source_type=str(source_type),
                source_ref=source_ref,
                team="",
                sprint=0,
                ordinal=ordinal,
                text=text,
                score=1.0 - float(distance),  # cosine distance -> similarity
            )
            for source_type, source_ref, ordinal, text, distance in rows
        ]

    def close(self) -> None:
        self._conn.close()
