"""Run corpus ingestion.

    DATABASE_URL=postgresql://... .venv/bin/python scripts/ingest.py

With DATABASE_URL set, ingests into Postgres+pgvector; otherwise into an in-memory store
(useful for a dry run). The embedder is chosen by `make_embedder()`: offline `HashingEmbedder`
by default; set `SPRINTSIGHT_EMBEDDER=local` (with the `[embed]` extra) for the real in-region
model (decision D1). IMPORTANT: query the same embedder you ingest with — change the embedder,
re-ingest (see docs/embedder/real-embedder.md). Prints a machine-parseable `RESULT {json}` line
with the ingest report and resulting DB row counts.
"""

import json
import os
import sys

from sprintsight.config import load_env
from sprintsight.ingest import ingest_corpus
from sprintsight.ingest.embedding import make_embedder
from sprintsight.ingest.store import InMemoryStore, PostgresStore


def main() -> int:
    load_env()
    dsn = os.getenv("DATABASE_URL")
    store = PostgresStore(dsn) if dsn else InMemoryStore()
    try:
        report = ingest_corpus(store, make_embedder())
        counts = store.counts()
    finally:
        store.close()

    result = {**report.as_dict(), **{f"db_{k}": v for k, v in counts.items()}}
    print("RESULT " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
