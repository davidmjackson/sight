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
