"""The ingestion pipeline: parse -> chunk -> embed -> store, idempotently."""

import hashlib
from dataclasses import dataclass

from sprintsight.evals.fixtures import Artifact, load_corpus
from sprintsight.ingest.chunking import chunk_text
from sprintsight.ingest.embedding import Embedder
from sprintsight.ingest.store import ArtifactInput, Store


@dataclass
class IngestReport:
    artifacts_total: int = 0
    ingested: int = 0          # newly inserted or changed (re-chunked)
    skipped: int = 0           # unchanged (content_hash match)
    chunks_written: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "artifacts_total": self.artifacts_total,
            "ingested": self.ingested,
            "skipped": self.skipped,
            "chunks_written": self.chunks_written,
        }


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def ingest_corpus(
    store: Store,
    embedder: Embedder,
    artifacts: dict[str, Artifact] | None = None,
    max_chars: int = 800,
) -> IngestReport:
    """Ingest every artifact into `store`, chunking + embedding changed ones only.

    Idempotent: an artifact whose body hash matches what's already stored is skipped, so
    re-running adds no rows.
    """
    artifacts = load_corpus() if artifacts is None else artifacts
    report = IngestReport(artifacts_total=len(artifacts))

    for art in artifacts.values():
        source_type = art.source_type
        source_ref = art.meta.get("source_ref", art.artifact_id)
        content_hash = _content_hash(art.body)

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
            )
        )

        chunks = chunk_text(art.body, max_chars=max_chars)
        vectors = embedder.embed([c.text for c in chunks])
        report.chunks_written += store.replace_chunks(
            artifact_id, list(zip(chunks, vectors, strict=True))
        )
        report.ingested += 1

    return report
