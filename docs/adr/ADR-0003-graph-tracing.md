# ADR-0003: Per-node graph tracing via optional Tracer

- **Story:** SS-7
- **Status:** Accepted
- **Date:** 2026-06-19
- **Deciders:** David (owner)

## Context

Stage 3 wired the three-node LangGraph graph (retrieval, risk, report_writer). Eval runs
are already traced via the `Tracer` protocol and `NoOpTracer` in `sprintsight/evals/tracing.py`,
but the graph's own nodes emit no spans. When an eval fails it is hard to tell which node
produced the bad output, how long it took, or what state it received.

Stage 4 adds Langfuse observability. The first step is to make one graph run emit a parent
`graph:run` span containing three `node:<name>` child spans, reusing the existing tracing
adapter so no new dependency is needed.

## Decision

`build_graph` and `run` in `sprintsight/graph/builder.py` now accept an optional
`tracer: Tracer | None` parameter.

- `build_graph` defaults to `NoOpTracer()`. Each node is wrapped in a `_traced` closure that
  opens a `node:<name>` span on every invocation.
- `run` defaults to `get_tracer()`, which returns a real Langfuse tracer when
  `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, and a `NoOpTracer` otherwise. The
  whole invoke is wrapped in a `graph:run` span; `flush()` is called in a `finally` block so
  spans are never lost on error.

No changes are made to `nodes.py`, `detector.py`, `report/`, or `retrieval/`.

## Consequences

**Positive**

- End-to-end observability of a run: one trace per graph invoke, three child spans, each
  carrying the node name and its wall-clock time (when Langfuse is configured).
- Diagnosing eval failures is faster because the failing node is immediately visible in
  Langfuse rather than requiring a debug rerun with added logging.
- Reuses the existing `Tracer` protocol and `NoOpTracer` without adding any dependency.
- The default path is identical to Stage 3: no Langfuse keys, no network calls, no behaviour
  change. All existing tests pass unchanged.

**Negative / risks**

- `build_graph` now takes a `tracer` argument. Callers that construct the graph directly
  (rather than through `run`) must pass a tracer explicitly if they want spans, or accept the
  no-op default.
- `_traced` wraps each node in a closure. The overhead is negligible for a no-op tracer
  (one Python function call per node per run).

## Data and privacy

Spans carry the node name and timing only. Report text and team IDs are visible in Langfuse
only when the operator configures Langfuse credentials. Zero Data Retention (ZDR) is the
required configuration for client data, consistent with the existing tracing approach in
`tracing.py`.

## Links

- ADR-0001: Three-node graph structure.
- `sprintsight/evals/tracing.py`: `Tracer`, `NoOpTracer`, `get_tracer`.
- `sprintsight/graph/builder.py`: implementation.
- `tests/test_graph_tracing.py`: `RecordingTracer` test fixture and assertions.
