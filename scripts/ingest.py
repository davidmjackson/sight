"""Run corpus ingestion.

    DATABASE_URL=postgresql://... .venv/bin/python scripts/ingest.py

With DATABASE_URL set, ingests into Postgres+pgvector; otherwise into an in-memory store
(useful for a dry run). Uses the offline HashingEmbedder so no embedding-model credentials
are needed (the real in-region model — decision D1 — is finalised in a later step). Prints a
machine-parseable `RESULT {json}` line with the ingest report and resulting DB row counts.
"""

import json
import os
import sys

from sprintsight.ingest import ingest_corpus
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.ingest.store import InMemoryStore, PostgresStore


def main() -> int:
    dsn = os.getenv("DATABASE_URL")
    store = PostgresStore(dsn) if dsn else InMemoryStore()
    try:
        report = ingest_corpus(store, HashingEmbedder())
        counts = store.counts()
    finally:
        store.close()

    result = {**report.as_dict(), **{f"db_{k}": v for k, v in counts.items()}}
    print("RESULT " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
