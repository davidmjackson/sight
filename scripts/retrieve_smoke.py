"""Smoke-test the Postgres+pgvector retrieval path (run in CI after ingestion).

    DATABASE_URL=postgresql://... .venv/bin/python scripts/retrieve_smoke.py

Embeds a query with the offline HashingEmbedder, runs a cosine-distance search, and asserts
it returns ranked results carrying provenance. Proves the pgvector search + artifact join
work on a real database. Exits non-zero on failure.
"""

import os
import sys

from sprintsight.config import load_env
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.retrieval.postgres import PostgresRetriever

VALID_SOURCE_TYPES = {"jira", "confluence", "slack", "raid", "other"}


def main() -> int:
    load_env()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set")
        return 2

    retriever = PostgresRetriever(dsn)
    try:
        results = retriever.search("dependency slipped auth api blocked", HashingEmbedder(), k=5)
    finally:
        retriever.close()

    if not results:
        print("FAIL: retrieval returned no results")
        return 1
    for r in results:
        if r.source_type not in VALID_SOURCE_TYPES or not r.source_ref:
            print(f"FAIL: missing/invalid provenance on result: {r}")
            return 1
    # Cosine distance in [0, 2] -> similarity in [-1, 1]; ranked descending.
    scores = [r.score for r in results]
    if scores != sorted(scores, reverse=True):
        print(f"FAIL: results not ranked by score: {scores}")
        return 1

    print(
        f"OK — retrieved {len(results)} chunks with provenance; "
        f"top source_ref={results[0].source_ref}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
