# Stage 3 — LangGraph three-node graph (orchestration)

- **Date:** 2026-06-18
- **Stage:** 3 (multi-agent orchestration)
- **Status:** Design approved — ready for implementation plan
- **Relates to:** ADR-0001 (three-node cut); builds on Stage 1 (retrieval/detector) and Stage 2 (report-writer seam)

## 1. Goal & scope decision

Wire the three components built in Stages 1–2 into the LangGraph graph specified by
ADR-0001: **retrieval → risk/reconciliation → report-writer**. This Stage is **pure
orchestration** — it introduces **no new model behaviour**. The existing functions
(`detect`, the `ReportWriter` seam, `Retriever`) are wrapped as graph nodes over a shared
state and run in sequence.

Scope was fixed during brainstorming (2026-06-18):

- **Orchestration-only.** `detect` and `compose`/`make_llm_writer` keep reading the
  `artifacts` dict by deterministic id. The retrieval node runs *alongside* that flow and
  parks its output in state; rewiring downstream to consume retrieved chunks is **deferred**.
- **Eval gate = run the existing evals through the graph.** The watermelon eval and the
  report-quality eval are re-pointed at the graph entrypoint, so the locked behaviours
  (4/4 + 4/4 watermelon, 4/4 report) must survive the wiring.
- **Retrieval node does real retrieval, parked in state.** A genuine working RAG node
  (`InMemoryRetriever` + `HashingEmbedder`, no API), not a placeholder.

## 2. Architecture & module layout

A new package `sprintsight/graph/` holds all orchestration. **Nothing in `detector.py`,
`report/`, or `retrieval/` changes.**

```
sprintsight/graph/
  __init__.py
  state.py    # GraphState TypedDict — the shared state
  nodes.py    # retrieval_node, risk_node, report_writer_node
  builder.py  # build_graph(writer=compose, retriever=None) -> compiled graph
              # + run(team, audience, artifacts, ...) convenience wrapper
```

**Graph shape:** linear — `START → retrieval → risk → report_writer → END`. No
branching/conditional edges (YAGNI); the thin-data case is handled *inside* the risk node.

**Dependency:** add `langgraph` to core `dependencies` in `pyproject.toml` (first use).
Raw LangGraph `StateGraph` + `TypedDict` state — **not** LangChain, per the tech-stack rule
(CLAUDE.md). LangGraph is the only new runtime dependency.

**Injection (preserves the seams and keeps CI off the Anthropic API):**

- `build_graph(writer: ReportWriter = compose)` — the default and CI use the deterministic
  `compose`; the `--llm` eval path passes `make_llm_writer()`. The report-writer node simply
  calls the injected `writer`.
- The retriever is built per-run *inside* the retrieval node from the team's own artifacts
  (`InMemoryRetriever` + `HashingEmbedder` — no API, CI-safe). `build_graph` accepts an
  optional `make_retriever: Callable[[dict[str, Artifact]], Retriever]` builder hook
  (defaulting to the in-memory builder) so tests can substitute a fake.

The graph is a thin orchestration shell over functions already built and trusted.

## 3. Graph state

A single `TypedDict` threaded through the nodes. Inputs are set at invocation; each node
writes only its own slice.

```python
class GraphState(TypedDict):
    # --- inputs (set when the graph is invoked) ---
    team: str
    audience: str                       # "exec" | "programme" | "team"
    artifacts: dict[str, Artifact]      # full corpus dict, keyed by id — passes through untouched

    # --- written by nodes ---
    retrieved: list[RetrievedChunk]     # retrieval_node — parked for observability/Stage-4, not yet consumed
    verdict: Verdict | None             # risk_node — None for thin-data teams (e.g. Echo)
    report: Report                      # report_writer_node — the audience-tuned output
```

Deliberate points:

- **`artifacts` is never mutated.** `detect` and `compose` keep reading it by deterministic
  id exactly as today — that is *why* the existing evals stay green through the graph. The
  retrieval node reads it to build its index but writes only `retrieved`.
- **`verdict: Verdict | None`** — the risk node sets `None` when a team lacks the data to
  judge (thin-data Echo), so running the report eval through the graph does not crash on a
  team the watermelon detector was never meant to score.

Each eval reads the slice it cares about: watermelon → `state["verdict"]`,
report → `state["report"]`.

## 4. The three nodes

Each node is a thin adapter: read inputs from state, call an existing function, write one
slice back. No business logic moves into the graph.

### 4.1 `retrieval_node` (genuine RAG node, CI-safe, no API)

- Builds an in-memory index from *this team's* artifacts via the existing ingest path
  (chunk → `HashingEmbedder` → `InMemoryRetriever`).
- Runs a team-scoped status query (e.g. `"{team} sprint status risks delivery"`), takes the
  top-k chunks (default `k=5`, parameterised on `build_graph`) → `state["retrieved"]`.
- Does **not** touch `artifacts`. A log line records that chunks are parked (retrieved but
  not yet consumed downstream) — honest about the deferred wiring, Stage-4-ready.

### 4.2 `risk_node` (recommend-only reconciliation, unchanged logic)

- Thin-data guard first: if `burndown-{team}-s15` is absent, set `verdict = None` and return
  (this is what lets Echo flow through without a `KeyError` in `detect`).
- Otherwise `verdict = detect({"team": ..., "artifacts": ...})`. **No RAID writes** (moat B3),
  exactly as today.

### 4.3 `report_writer_node` (the injected seam)

- `report = writer({"team": ..., "audience": ..., "artifacts": ...})` where `writer` is
  whatever was passed to `build_graph` (`compose` by default; `make_llm_writer()` on the
  `--llm` path).
- All grounding/citation/fabrication guarantees live in the writer already — the node adds
  nothing that could weaken them.

## 5. Eval gate, error handling & testing

### 5.1 Eval gate (eval-first; makes the Story Done)

Re-point both existing evals at the graph entrypoint so the locked behaviours must survive
the wiring:

- **Watermelon eval** → invokes the graph per case, reads `state["verdict"]`. Must stay
  **4/4 classification + 4/4 evidence** (4 full teams: Atlas, Boreas, Cygnus, Draco).
- **Report-quality eval** → invokes the graph per case, reads `state["report"]`. Must stay
  **4/4** (5 cases incl. Echo). The `--llm` flag builds the graph with `make_llm_writer()`;
  the default builds it with `compose`.
- Both runner scripts (`scripts/run_watermelon_eval.py`, `scripts/run_report_eval.py`)
  switch from calling the functions directly to invoking `build_graph(...)`. The eval
  **assertions do not change** — only the thing under test does.

### 5.2 Graph structure/smoke test (new, thin)

- Graph compiles; has exactly 3 nodes + linear edges.
- A full-team run populates `retrieved` + `verdict` + `report`.
- An Echo run yields `verdict is None` and an `insufficient_evidence` report **without
  crashing**.
- `retrieved` is non-empty for a normal team.

### 5.3 CI

`lint-and-test` keeps running both evals (now through the graph) — still **never calls the
API** (default `compose`; Anthropic import stays lazy/absent on the default path). No CI
change beyond the dependency install picking up `langgraph`.

### 5.4 Error handling

- Thin data (missing burndown) → `risk_node` sets `verdict=None`; the writer already emits
  `insufficient_evidence`. Handled in-node, no graph branch.
- LLM/section failures on the `--llm` path → existing per-section fallback in
  `make_llm_writer` is untouched.
- Retrieval over a sparse team → returns whatever chunks exist; never fatal.

## 6. Scope boundary (YAGNI)

**In scope:** the `sprintsight/graph/` package (state + 3 nodes + builder), the `langgraph`
dependency, both eval runners re-pointed through the graph, the graph smoke test, a Stage-3
Jira Story.

**Explicitly deferred (not this Story):**

- Consuming `retrieved` chunks downstream — `detect`/`compose` keep reading by id; rewiring
  is a later, eval-first change.
- Promoting planner / analysis / critic to nodes — only when an eval triggers ADR-0001's
  revisit criteria.
- Postgres-backed retriever *in the graph* — `InMemoryRetriever` for the showcase (the
  Postgres path still exists for the `db` CI job).
- LangGraph checkpointer / persistence / human-in-the-loop interrupts; conditional/branching
  edges.

## 7. Board

Open a Stage-3 Story at implementation time, confirming the right Epic from
`docs/jira/epic-key-map.md` first (the report-writer node SS-28 sat under SS-1 "Status
Report Agent"; the orchestration Epic is likely distinct). Created in Backlog/To Do,
transitioned to In Progress when work starts, In Review for the eval run — never Done on
create (per CLAUDE.md / docs/jira/workflow.md).
