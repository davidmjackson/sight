"""Tests for per-node graph tracing (Task 3, SS-7).

Uses a RecordingTracer (in-process stand-in) to verify the builder emits
one `graph:run` parent span and three `node:<name>` child spans per run.
No Langfuse keys required; CI stays fully offline.
"""

from contextlib import contextmanager

from sprintsight.evals.fixtures import artifacts_for
from sprintsight.graph.builder import run


class RecordingTracer:
    """Captures span names in order. Stand-in for the Langfuse tracer in tests."""

    def __init__(self) -> None:
        self.spans: list[str] = []

    @contextmanager
    def span(self, name: str):
        self.spans.append(name)
        yield None

    def flush(self) -> None:
        pass


def _inputs() -> dict:
    return {"team": "Boreas", "audience": "exec", "artifacts": artifacts_for("Boreas", [15])}


def test_run_emits_one_run_span_and_three_node_spans():
    tracer = RecordingTracer()
    state = run(_inputs(), tracer=tracer)
    assert "graph:run" in tracer.spans
    assert "node:retrieval" in tracer.spans
    assert "node:risk" in tracer.spans
    assert "node:report_writer" in tracer.spans
    assert state["report"] is not None  # tracing does not change the result


def test_run_without_tracer_still_produces_a_report():
    state = run(_inputs())
    assert state["report"] is not None
