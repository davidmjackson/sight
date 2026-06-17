"""In-memory vector retriever and the shared retrieval contract.

`InMemoryRetriever` indexes the corpus (same chunker as ingestion) with full provenance,
including the corpus `artifact_id` and team/sprint — which the watermelon detector needs to
cite evidence. Ranking is cosine similarity. Team/sprint scoping is applied before ranking.

Note: with the offline `HashingEmbedder` (a non-semantic stand-in) similarity is exact-match
oriented, not semantic — natural-language recall quality arrives with the real in-region
embedding model (decision D1). The retrieval *mechanism* (ranking, scoping, provenance) is
model-independent and fully exercised here.
"""

import math
from dataclasses import dataclass
from typing import Protocol

from sprintsight.evals.fixtures import Artifact, load_corpus
from sprintsight.ingest.chunking import chunk_text
from sprintsight.ingest.embedding import Embedder


@dataclass(frozen=True)
class IndexedChunk:
    artifact_id: str
    source_type: str
    source_ref: str
    team: str
    sprint: int
    ordinal: int
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class RetrievedChunk:
    artifact_id: str
    source_type: str
    source_ref: str
    team: str
    sprint: int
    ordinal: int
    text: str
    score: float


class Retriever(Protocol):
    def search(
        self,
        query: str,
        k: int = 5,
        team: str | None = None,
        sprints: list[int] | None = None,
    ) -> list[RetrievedChunk]: ...


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class InMemoryRetriever:
    """Builds an in-memory chunk index from the corpus and ranks by cosine similarity."""

    def __init__(
        self,
        embedder: Embedder,
        artifacts: dict[str, Artifact] | None = None,
        max_chars: int = 800,
    ) -> None:
        self.embedder = embedder
        self.index: list[IndexedChunk] = []
        artifacts = load_corpus() if artifacts is None else artifacts
        for art in artifacts.values():
            chunks = chunk_text(art.body, max_chars=max_chars)
            vectors = embedder.embed([c.text for c in chunks])
            for c, vec in zip(chunks, vectors, strict=True):
                self.index.append(
                    IndexedChunk(
                        artifact_id=art.artifact_id,
                        source_type=art.source_type,
                        source_ref=art.meta.get("source_ref", art.artifact_id),
                        team=art.team,
                        sprint=art.sprint,
                        ordinal=c.ordinal,
                        text=c.text,
                        embedding=vec,
                    )
                )

    def search(
        self,
        query: str,
        k: int = 5,
        team: str | None = None,
        sprints: list[int] | None = None,
    ) -> list[RetrievedChunk]:
        q = self.embedder.embed([query])[0]
        candidates = [
            ic
            for ic in self.index
            if (team is None or ic.team.lower() == team.lower())
            and (sprints is None or ic.sprint in sprints)
        ]
        ranked = sorted(candidates, key=lambda ic: cosine(q, ic.embedding), reverse=True)
        return [
            RetrievedChunk(
                artifact_id=ic.artifact_id,
                source_type=ic.source_type,
                source_ref=ic.source_ref,
                team=ic.team,
                sprint=ic.sprint,
                ordinal=ic.ordinal,
                text=ic.text,
                score=cosine(q, ic.embedding),
            )
            for ic in ranked[:k]
        ]
