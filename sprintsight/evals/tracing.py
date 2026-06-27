"""Optional Langfuse tracing for eval runs (Langfuse SDK v4).

Langfuse is the observability/eval backend (per the stack). Wiring is kept strictly
optional AND opt-in: tracing is off unless SPRINTSIGHT_TRACE=on AND LANGFUSE_PUBLIC_KEY /
LANGFUSE_SECRET_KEY are set (the v4 client reads the keys itself). Without all three —
or with the package not installed — the harness uses a no-op tracer, so evals run
identically in CI and a developer's .env keys do not silently ship events (and burn the
Langfuse free-tier quota) on every local run. Flip the flag on only to inspect a run.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol


class Tracer(Protocol):
    """Minimal tracing surface the harness depends on."""

    def span(self, name: str) -> "object": ...
    def flush(self) -> None: ...


class NoOpTracer:
    """Used when Langfuse is unavailable or unconfigured. Does nothing, costs nothing."""

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        yield None

    def flush(self) -> None:
        pass


class LangfuseTracer:
    """Adapter over a Langfuse v4 client. Each span becomes an observation/trace."""

    def __init__(self, client: object) -> None:
        self._client = client

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        # start_as_current_observation is itself a context manager in v4.
        with self._client.start_as_current_observation(name=name, as_type="span"):
            yield None

    def flush(self) -> None:
        flush = getattr(self._client, "flush", None)
        if callable(flush):
            flush()


_TRACE_FLAG = "SPRINTSIGHT_TRACE"


def _enabled() -> bool:
    """Opt-in: trace only when the flag is on AND both Langfuse keys are present (fail-safe)."""
    return (
        os.getenv(_TRACE_FLAG) == "on"
        and bool(os.getenv("LANGFUSE_PUBLIC_KEY"))
        and bool(os.getenv("LANGFUSE_SECRET_KEY"))
    )


def get_tracer() -> Tracer:
    """Return a Langfuse-backed tracer only when explicitly enabled + installed, else a no-op."""
    if not _enabled():
        return NoOpTracer()
    try:
        from langfuse import get_client  # type: ignore[import-not-found]
    except ImportError:
        return NoOpTracer()
    return LangfuseTracer(get_client())
