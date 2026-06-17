"""Optional Langfuse tracing for eval runs.

Langfuse is the observability/eval backend (per the stack). It is wired here but kept
strictly optional: with no credentials configured — or the package not installed — the
harness uses a no-op tracer so evals run identically in CI. When LANGFUSE_PUBLIC_KEY /
LANGFUSE_SECRET_KEY are set, runs are traced.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol


class Tracer(Protocol):
    """Minimal tracing surface the harness depends on."""

    def span(self, name: str) -> "object": ...


class NoOpTracer:
    """Used when Langfuse is unavailable or unconfigured. Does nothing, costs nothing."""

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        yield None


class LangfuseTracer:
    """Thin adapter over a Langfuse client. Each span becomes a trace event."""

    def __init__(self, client: object) -> None:
        self._client = client

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        # Langfuse client APIs vary by version; trace best-effort and never fail the run.
        start = getattr(self._client, "trace", None)
        handle = start(name=name) if callable(start) else None
        try:
            yield None
        finally:
            end = getattr(handle, "end", None)
            if callable(end):
                end()


def _configured() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def get_tracer() -> Tracer:
    """Return a Langfuse-backed tracer if configured and installed, else a no-op tracer."""
    if not _configured():
        return NoOpTracer()
    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]
    except ImportError:
        return NoOpTracer()
    return LangfuseTracer(Langfuse())
