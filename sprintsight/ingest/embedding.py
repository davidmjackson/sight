"""Embedding interface + a deterministic offline embedder + the real in-region model (D1).

`HashingEmbedder` produces deterministic 1024-dim unit vectors with no network or model
dependency, so ingestion and its tests run fully offline; it is NOT semantic (it hashes the
whole string). `LocalEmbedder` is the real, self-hostable, in-region model (schema decision D1,
output locked at 1024 dims to match `chunk.embedding vector(1024)`); it lazy-imports
`sentence-transformers` from the optional `[embed]` extra so importing this module stays
dependency-free. Both satisfy the `Embedder` protocol. `make_embedder()` picks between them from
the environment (offline-by-default, real model opt-in), the same fail-safe gate pattern used for
the DB, the LLM writer, the judge, and the live connectors.

CORRECTNESS TRAP: stored chunk vectors and a query vector are only comparable if the SAME embedder
(and model id) produced both. Always ingest and query with the same `SPRINTSIGHT_EMBEDDER` /
`SPRINTSIGHT_EMBED_MODEL`; if you change the embedder, re-ingest. See
docs/embedder/real-embedder.md.
"""

import hashlib
import math
import os
from typing import Protocol

EMBEDDING_DIM = 1024
DEFAULT_LOCAL_MODEL = "thenlper/gte-large"  # 1024-dim native, no query/passage prefix asymmetry


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic, dependency-free embedder. NOT semantic — a dev/CI stand-in only."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        data = text.encode("utf-8")
        while len(values) < self.dim:
            block = hashlib.sha256(data + counter.to_bytes(4, "big")).digest()
            for i in range(0, len(block), 4):
                if len(values) >= self.dim:
                    break
                n = int.from_bytes(block[i : i + 4], "big")
                values.append((n / 2**32) * 2.0 - 1.0)  # map to [-1, 1)
            counter += 1
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


class LocalEmbedder:
    """Real, self-hostable, in-region embedding model (D1). Semantic, 1024-dim, L2-normalized.

    `sentence-transformers` (the `[embed]` extra) is imported lazily and the model is loaded once,
    on the first `.embed()` call, so constructing this object is cheap and dependency-free (the
    factory can pick it without paying the import/download). No text leaves the host.
    """

    def __init__(self, model_id: str = DEFAULT_LOCAL_MODEL, dim: int = EMBEDDING_DIM) -> None:
        self.model_id = model_id
        self.dim = dim
        self._model = None  # loaded lazily on first embed()

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "LocalEmbedder needs the 'embed' extra: pip install '.[embed]' "
                "(installs sentence-transformers)."
            ) from exc
        model = SentenceTransformer(self.model_id)
        actual = model.get_sentence_embedding_dimension()
        if actual != self.dim:
            raise ValueError(
                f"Embedding model {self.model_id!r} outputs {actual} dims, but the schema "
                f"locks {self.dim} (chunk.embedding vector({self.dim})). Choose a {self.dim}-dim "
                "model or migrate the column."
            )
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._ensure_model()
        vectors = self._model.encode(
            list(texts), normalize_embeddings=True, convert_to_numpy=True
        )
        return [v.tolist() for v in vectors]


def make_embedder(env: dict[str, str] | None = None) -> Embedder:
    """Pick the embedder from the environment (offline-by-default, real model opt-in).

    `SPRINTSIGHT_EMBEDDER=local` selects the real `LocalEmbedder` (model id from
    `SPRINTSIGHT_EMBED_MODEL`, default `thenlper/gte-large`); anything else keeps the offline
    `HashingEmbedder` stand-in. Used by the ingest + retrieve scripts so BOTH sides use the same
    embedder (see the correctness trap in the module docstring).
    """
    env = os.environ if env is None else env
    if env.get("SPRINTSIGHT_EMBEDDER", "").strip().lower() == "local":
        return LocalEmbedder(env.get("SPRINTSIGHT_EMBED_MODEL", DEFAULT_LOCAL_MODEL))
    return HashingEmbedder()
