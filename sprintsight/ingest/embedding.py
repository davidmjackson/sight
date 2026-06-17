"""Embedding interface + a deterministic offline embedder.

The production embedder is a self-hostable, in-region model with a fixed 1024-dim output
(schema decision D1; exact model finalised under eval in a later Stage-1 step). Until then
`HashingEmbedder` produces deterministic 1024-dim unit vectors with no network or model
dependency, so ingestion and its tests run fully offline. Both satisfy the `Embedder`
protocol, so swapping in the real model is a one-line change at the call site.
"""

import hashlib
import math
from typing import Protocol

EMBEDDING_DIM = 1024


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
