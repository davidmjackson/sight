"""RAG retrieval (SS-2.6) — the ADR-0001 retrieval node.

Vector-similarity search over chunks, returning ranked, cited results. `InMemoryRetriever`
is the functional offline retriever (used by the watermelon detector and tests, with
team/sprint scoping and full provenance). `PostgresRetriever` is the production path over
Postgres+pgvector. Both implement the `Retriever` protocol.
"""

from sprintsight.retrieval.retriever import (
    IndexedChunk,
    InMemoryRetriever,
    RetrievedChunk,
    Retriever,
)

__all__ = ["IndexedChunk", "InMemoryRetriever", "RetrievedChunk", "Retriever"]
