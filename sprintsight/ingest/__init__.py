"""Ingestion pipeline (SS-2.5): parse corpus artifacts -> chunk -> embed -> store.

Storage and embedding are injected (see `store` and `embedding`) so the pipeline runs
identically against an in-memory store + offline embedder (tests/CI) or Postgres+pgvector
and a real in-region embedding model (deployment).
"""

from sprintsight.ingest.pipeline import IngestReport, ingest_corpus

__all__ = ["IngestReport", "ingest_corpus"]
