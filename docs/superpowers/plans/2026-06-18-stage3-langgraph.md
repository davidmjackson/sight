# Stage 3 — LangGraph Three-Node Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the three Stage 1–2 components (retrieval, watermelon detector, report-writer) into a linear LangGraph graph per ADR-0001, with the existing watermelon and report-quality evals re-pointed to run *through* the graph as the gate.

**Architecture:** A new `sprintsight/graph/` package holds a `StateGraph` over a shared `TypedDict` state. Three thin node functions adapt existing functions (`detect`, the injected `ReportWriter`, `InMemoryRetriever`) — no business logic moves into the graph, and `detector.py`/`report/`/`retrieval/` are not modified. The graph runs `retrieval → risk → report_writer` linearly; the retrieval node does real CI-safe retrieval parked in state and is not yet consumed downstream.

**Tech Stack:** Python 3.11, LangGraph (raw `StateGraph`, not LangChain), pytest, ruff. Offline-only on the default path (`HashingEmbedder`, `compose`) — CI never calls the Anthropic API.

## Global Constraints

- Python 3.11; ruff lint clean (`select = ["E","F","I","UP","B"]`, line-length 100).
- New core dependency: `langgraph>=0.2` added to `[project].dependencies` in `pyproject.toml` (no upper bound, matching the repo's `anthropic>=0.40` style).
- **Do not modify** `sprintsight/detector.py`, `sprintsight/report/*`, or `sprintsight/retrieval/*`. Stage 3 is orchestration-only.
- `artifacts` dict is never mutated; `detect`/`compose` keep reading by deterministic id.
- The default path uses `compose` and `HashingEmbedder` — **no Anthropic import on the default path**. The `--llm` path stays key-gated exactly as today (exit 2 without a real key).
- Recommend-only: the risk node never writes to a RAID log (moat B3).
- Existing eval bars must hold through the graph: watermelon 4/4 classification + 4/4 evidence; report-quality 4/4.
- Frequent commits: one commit per task.

---

### Task 1: Graph state + node functions

**Files:**
- Modify: `pyproject.toml` (add `langgraph>=0.2` to `[project].dependencies`)
- Create: `sprintsight/graph/__init__.py`
- Create: `sprintsight/graph/state.py`
- Create: `sprintsight/graph/nodes.py`
- Test: `tests/test_graph_nodes.py`

**Interfaces:**
- Consumes (existing, unchanged):
  - `sprintsight.detector.detect(inputs: dict) -> Verdict` where `inputs = {"team", "artifacts"}`
  - `sprintsight.report.writer.ReportWriter = Callable[[dict], Report]`, `compose(inputs) -> Report`
  - `sprintsight.retrieval.retriever.Retriever` protocol with `.search(query, k=5, team=None, sprints=None) -> list[RetrievedChunk]`
  - `sprintsight.evals.fixtures.Artifact`, `artifacts_for(team, sprints) -> dict[str, Artifact]`
  - `sprintsight.evals.watermelon.Verdict`, `sprintsight.report.contract.Report`
- Produces (for Task 2):
  - `sprintsight.graph.state.GraphState` (TypedDict, `total=False`) and `DEFAULT_AUDIENCE = "programme"`
  - `sprintsight.graph.nodes.retrieval_node(state, *, make_retriever, k=5) -> dict`
  - `sprintsight.graph.nodes.risk_node(state) -> dict`
  - `sprintsight.graph.nodes.report_writer_node(state, *, writer) -> dict`
  - `sprintsight.graph.nodes.RetrieverFactory = Callable[[dict[str, Artifact]], Retriever]`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, change the `dependencies` list to:

```toml
dependencies = [
  "pyyaml>=6",
  "anthropic>=0.40",
  "langgraph>=0.2",
]
```

Then install it:

Run: `.venv/bin/pip install -e ".[dev]"`
Expected: installs `langgraph` and its deps; no errors.

- [ ] **Step 2: Create the package + state**

Create `sprintsight/graph/__init__.py`:

```python
"""Stage 3 LangGraph orchestration: retrieval -> risk -> report-writer (ADR-0001)."""
```

Create `sprintsight/graph/state.py`:

```python
"""The shared graph state threaded through the three nodes (Stage 3, ADR-0001).

`total=False` so each node may contribute only its own slice — inputs (team/
audience/artifacts) are set at invocation; nodes add retrieved/verdict/report.
`artifacts` is read-only and passes through untouched, which is why the existing
evals stay green through the graph.
"""

from typing import TypedDict

from sprintsight.evals.fixtures import Artifact
from sprintsight.evals.watermelon import Verdict
from sprintsight.report.contract import Report
from sprintsight.retrieval.retriever import RetrievedChunk

DEFAULT_AUDIENCE = "programme"


class GraphState(TypedDict, total=False):
    # inputs (set when the graph is invoked)
    team: str
    audience: str
    artifacts: dict[str, Artifact]
    # written by nodes
    retrieved: list[RetrievedChunk]
    verdict: Verdict | None
    report: Report
```

- [ ] **Step 3: Write the failing node tests**

Create `tests/test_graph_nodes.py`:

```python
from sprintsight.detector import detect
from sprintsight.evals.fixtures import artifacts_for
from sprintsight.graph.nodes import report_writer_node, retrieval_node, risk_node
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.report.writer import compose
from sprintsight.retrieval.retriever import InMemoryRetriever


def _make_retriever(artifacts):
    return InMemoryRetriever(HashingEmbedder(), artifacts=artifacts)


def test_retrieval_node_returns_chunks():
    arts = artifacts_for("Boreas", [14, 15])
    out = retrieval_node({"team": "Boreas", "artifacts": arts}, make_retriever=_make_retriever, k=5)
    assert "retrieved" in out
    assert len(out["retrieved"]) > 0
    assert all(c.team.lower() == "boreas" for c in out["retrieved"])


def test_risk_node_full_team_matches_detect():
    arts = artifacts_for("Atlas", [14, 15])
    out = risk_node({"team": "Atlas", "artifacts": arts})
    assert out["verdict"] == detect({"team": "Atlas", "artifacts": arts})


def test_risk_node_thin_data_returns_none():
    arts = artifacts_for("Echo", [15])
    out = risk_node({"team": "Echo", "artifacts": arts})
    assert out["verdict"] is None


def test_report_writer_node_uses_injected_writer():
    arts = artifacts_for("Boreas", [15])
    state = {"team": "Boreas", "audience": "exec", "artifacts": arts}
    out = report_writer_node(state, writer=compose)
    assert out["report"] == compose({"team": "Boreas", "audience": "exec", "artifacts": arts})


def test_report_writer_node_defaults_audience():
    arts = artifacts_for("Boreas", [15])
    out = report_writer_node({"team": "Boreas", "artifacts": arts}, writer=compose)
    assert out["report"].audience == "programme"
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_graph_nodes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sprintsight.graph.nodes'`.

- [ ] **Step 5: Implement the nodes**

Create `sprintsight/graph/nodes.py`:

```python
"""The three graph nodes (Stage 3, ADR-0001). Thin adapters over existing functions.

Each node reads its inputs from the state and returns the single slice it owns.
No business logic lives here: retrieval delegates to a Retriever, risk to the
SS-2.7 detector (recommend-only, moat B3), the report node to the injected writer.
"""

import logging
from collections.abc import Callable

from sprintsight.detector import detect
from sprintsight.evals.fixtures import Artifact
from sprintsight.graph.state import DEFAULT_AUDIENCE, GraphState
from sprintsight.report.writer import ReportWriter
from sprintsight.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

RetrieverFactory = Callable[[dict[str, Artifact]], Retriever]


def retrieval_node(state: GraphState, *, make_retriever: RetrieverFactory, k: int = 5) -> dict:
    """Real, CI-safe retrieval over the team's artifacts. Chunks are parked in
    state for observability/Stage-4; they are NOT yet consumed downstream."""
    team = state["team"]
    retriever = make_retriever(state["artifacts"])
    chunks = retriever.search(f"{team} sprint status risks delivery", k=k, team=team)
    logger.info(
        "retrieval_node: %d chunks for %s (parked; not yet consumed downstream)",
        len(chunks),
        team,
    )
    return {"retrieved": chunks}


def risk_node(state: GraphState) -> dict:
    """Reconciliation / watermelon detection, recommend-only. Thin-data guard:
    a team with no Sprint-15 burndown cannot be scored, so verdict is None."""
    team = state["team"]
    artifacts = state["artifacts"]
    if f"burndown-{team.lower()}-s15" not in artifacts:
        logger.info("risk_node: insufficient data for %s; verdict=None", team)
        return {"verdict": None}
    return {"verdict": detect({"team": team, "artifacts": artifacts})}


def report_writer_node(state: GraphState, *, writer: ReportWriter) -> dict:
    """Audience-tuned report via the injected writer seam (compose / make_llm_writer)."""
    return {
        "report": writer(
            {
                "team": state["team"],
                "audience": state.get("audience", DEFAULT_AUDIENCE),
                "artifacts": state["artifacts"],
            }
        )
    }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_graph_nodes.py -v`
Expected: PASS (5 passed).

- [ ] **Step 7: Lint**

Run: `.venv/bin/ruff check sprintsight/graph tests/test_graph_nodes.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml sprintsight/graph/__init__.py sprintsight/graph/state.py sprintsight/graph/nodes.py tests/test_graph_nodes.py
git commit -m "feat(graph): Stage 3 graph state + three node functions (langgraph dep)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Graph builder + adapters

**Files:**
- Create: `sprintsight/graph/builder.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `GraphState`, `DEFAULT_AUDIENCE`, the three node functions + `RetrieverFactory` (Task 1); `langgraph.graph.{StateGraph, START, END}`; `InMemoryRetriever`, `HashingEmbedder`, `compose`.
- Produces (for Tasks 3–4):
  - `sprintsight.graph.builder.default_make_retriever(artifacts) -> Retriever`
  - `sprintsight.graph.builder.build_graph(writer=compose, make_retriever=default_make_retriever, k=5) -> CompiledStateGraph`
  - `sprintsight.graph.builder.run(inputs: dict, *, writer=compose, make_retriever=default_make_retriever, k=5) -> GraphState`
  - `sprintsight.graph.builder.graph_detector(*, make_retriever=default_make_retriever, k=5) -> Callable[[dict], Verdict]`
  - `sprintsight.graph.builder.graph_writer(writer=compose, *, make_retriever=default_make_retriever, k=5) -> Callable[[dict], Report]`

- [ ] **Step 1: Write the failing graph tests**

Create `tests/test_graph.py`:

```python
from sprintsight.detector import detect
from sprintsight.evals.fixtures import artifacts_for
from sprintsight.graph.builder import build_graph, graph_detector, graph_writer, run
from sprintsight.report.writer import compose


def test_graph_has_three_nodes():
    g = build_graph().get_graph()
    assert {"retrieval", "risk", "report_writer"} <= set(g.nodes)


def test_full_team_run_populates_state():
    inputs = {"team": "Boreas", "audience": "exec", "artifacts": artifacts_for("Boreas", [14, 15])}
    state = run(inputs)
    assert len(state["retrieved"]) > 0
    assert state["verdict"] is not None
    assert state["report"].audience == "exec"
    assert state["report"].insufficient_evidence is False


def test_thin_team_run_does_not_crash():
    inputs = {"team": "Echo", "audience": "exec", "artifacts": artifacts_for("Echo", [15])}
    state = run(inputs)
    assert state["verdict"] is None
    assert state["report"].insufficient_evidence is True


def test_graph_verdict_matches_detect():
    arts = artifacts_for("Atlas", [14, 15])
    state = run({"team": "Atlas", "artifacts": arts})
    assert state["verdict"] == detect({"team": "Atlas", "artifacts": arts})


def test_graph_report_matches_compose():
    arts = artifacts_for("Boreas", [15])
    state = run({"team": "Boreas", "audience": "exec", "artifacts": arts})
    assert state["report"] == compose({"team": "Boreas", "audience": "exec", "artifacts": arts})


def test_graph_detector_adapter_returns_verdict():
    arts = artifacts_for("Atlas", [14, 15])
    v = graph_detector()({"team": "Atlas", "artifacts": arts})
    assert v == detect({"team": "Atlas", "artifacts": arts})


def test_graph_writer_adapter_returns_report():
    arts = artifacts_for("Boreas", [15])
    r = graph_writer(compose)({"team": "Boreas", "audience": "exec", "artifacts": arts})
    assert r == compose({"team": "Boreas", "audience": "exec", "artifacts": arts})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_graph.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sprintsight.graph.builder'`.

- [ ] **Step 3: Implement the builder**

Create `sprintsight/graph/builder.py`:

```python
"""Builds and runs the Stage 3 LangGraph graph (ADR-0001).

Linear: START -> retrieval -> risk -> report_writer -> END. The writer and the
retriever factory are injected so the same graph serves CI (compose, offline)
and the live --llm path (make_llm_writer), and tests can substitute fakes.

`graph_detector` / `graph_writer` adapt the compiled graph back to the existing
eval seams (Detector / ReportWriter) so the watermelon and report evals run
THROUGH the graph unchanged.
"""

from collections.abc import Callable
from functools import partial

from langgraph.graph import END, START, StateGraph

from sprintsight.evals.fixtures import Artifact
from sprintsight.evals.watermelon import Verdict
from sprintsight.graph.nodes import (
    RetrieverFactory,
    report_writer_node,
    retrieval_node,
    risk_node,
)
from sprintsight.graph.state import DEFAULT_AUDIENCE, GraphState
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.report.contract import Report
from sprintsight.report.writer import ReportWriter, compose
from sprintsight.retrieval.retriever import InMemoryRetriever, Retriever


def default_make_retriever(artifacts: dict[str, Artifact]) -> Retriever:
    """Offline, CI-safe retriever built from just this team's artifacts."""
    return InMemoryRetriever(HashingEmbedder(), artifacts=artifacts)


def build_graph(
    writer: ReportWriter = compose,
    make_retriever: RetrieverFactory = default_make_retriever,
    k: int = 5,
):
    """Compile the linear three-node graph with the writer/retriever injected."""
    g = StateGraph(GraphState)
    g.add_node("retrieval", partial(retrieval_node, make_retriever=make_retriever, k=k))
    g.add_node("risk", risk_node)
    g.add_node("report_writer", partial(report_writer_node, writer=writer))
    g.add_edge(START, "retrieval")
    g.add_edge("retrieval", "risk")
    g.add_edge("risk", "report_writer")
    g.add_edge("report_writer", END)
    return g.compile()


def run(
    inputs: dict,
    *,
    writer: ReportWriter = compose,
    make_retriever: RetrieverFactory = default_make_retriever,
    k: int = 5,
) -> GraphState:
    """Invoke the graph for one {team, [audience], artifacts} input -> final state."""
    graph = build_graph(writer=writer, make_retriever=make_retriever, k=k)
    init: GraphState = {
        "team": inputs["team"],
        "audience": inputs.get("audience", DEFAULT_AUDIENCE),
        "artifacts": inputs["artifacts"],
    }
    return graph.invoke(init)


def graph_detector(
    *, make_retriever: RetrieverFactory = default_make_retriever, k: int = 5
) -> Callable[[dict], Verdict]:
    """Adapt the graph to the watermelon-eval Detector seam (inputs -> Verdict)."""

    def detect_via_graph(inputs: dict) -> Verdict:
        return run(inputs, make_retriever=make_retriever, k=k)["verdict"]

    return detect_via_graph


def graph_writer(
    writer: ReportWriter = compose,
    *,
    make_retriever: RetrieverFactory = default_make_retriever,
    k: int = 5,
) -> Callable[[dict], Report]:
    """Adapt the graph to the report-eval ReportWriter seam (inputs -> Report)."""

    def write_via_graph(inputs: dict) -> Report:
        return run(inputs, writer=writer, make_retriever=make_retriever, k=k)["report"]

    return write_via_graph
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_graph.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check sprintsight/graph/builder.py tests/test_graph.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/graph/builder.py tests/test_graph.py
git commit -m "feat(graph): Stage 3 graph builder + detector/writer adapters

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Re-point the watermelon eval through the graph

**Files:**
- Modify: `scripts/run_watermelon_eval.py`
- Test: `tests/test_graph_evals.py` (create)

**Interfaces:**
- Consumes: `graph_detector()` (Task 2); `sprintsight.evals.watermelon.run_watermelon_eval(detector)`.
- Produces: the watermelon eval now runs through the graph; `run_watermelon_eval(graph_detector())` has `pass_rate == 1.0`.

- [ ] **Step 1: Write the failing through-graph eval test**

Create `tests/test_graph_evals.py`:

```python
from sprintsight.evals.watermelon import run_watermelon_eval
from sprintsight.graph.builder import graph_detector


def test_watermelon_eval_green_through_graph():
    report = run_watermelon_eval(graph_detector())
    assert report.pass_rate == 1.0, report.summary()
```

- [ ] **Step 2: Run the test to verify it passes already**

The graph + adapter from Task 2 already make this green; this test pins it.

Run: `.venv/bin/pytest tests/test_graph_evals.py::test_watermelon_eval_green_through_graph -v`
Expected: PASS.

- [ ] **Step 3: Re-point the runner script**

Edit `scripts/run_watermelon_eval.py`. Replace the import line

```python
from sprintsight.detector import detect
```

with

```python
from sprintsight.graph.builder import graph_detector
```

and replace

```python
    report = run_watermelon_eval(detect)
```

with

```python
    report = run_watermelon_eval(graph_detector())
```

- [ ] **Step 4: Run the runner script end-to-end**

Run: `.venv/bin/python scripts/run_watermelon_eval.py`
Expected: prints the scoreboard, `pass_rate` 1.0, all 4 cases PASS; process exits 0.

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check scripts/run_watermelon_eval.py tests/test_graph_evals.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_watermelon_eval.py tests/test_graph_evals.py
git commit -m "feat(graph): run watermelon eval through the graph (4/4 via graph_detector)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Re-point the report-quality eval through the graph

**Files:**
- Modify: `scripts/run_report_eval.py`
- Modify: `tests/test_graph_evals.py` (add the report case)

**Interfaces:**
- Consumes: `graph_writer(writer)` (Task 2); `sprintsight.evals.report.run_report_eval(writer)`; `compose`, `make_llm_writer`.
- Produces: the report eval runs through the graph on both the default (`compose`) and `--llm` (`make_llm_writer()`) paths; default `pass_rate == 1.0`. CI never calls the API.

- [ ] **Step 1: Add the failing through-graph report test**

Edit `tests/test_graph_evals.py`. First, extend the import block at the **top** of the file to (keeps imports sorted and avoids ruff E402/F401):

```python
from sprintsight.evals.report import run_report_eval
from sprintsight.evals.watermelon import run_watermelon_eval
from sprintsight.graph.builder import graph_detector, graph_writer
from sprintsight.report.writer import compose
```

Then add this test at the **end** of the file:

```python
def test_report_eval_green_through_graph():
    report = run_report_eval(graph_writer(compose))
    assert report.pass_rate == 1.0, report.summary()
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_graph_evals.py::test_report_eval_green_through_graph -v`
Expected: PASS.

- [ ] **Step 3: Re-point the runner script**

Edit `scripts/run_report_eval.py`. Add this import alongside the existing writer imports:

```python
from sprintsight.graph.builder import graph_writer
```

Then change `_select_writer` so the chosen writer is wrapped by the graph adapter:

```python
def _select_writer() -> object:
    if "--llm" in sys.argv:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key.startswith("sk-ant-") or len(key) < 50:
            print("ERROR: --llm needs a real ANTHROPIC_API_KEY in the environment.")
            sys.exit(2)
        return graph_writer(make_llm_writer())
    return graph_writer(compose)
```

(The existing `make_llm_writer` and `compose` imports stay.)

- [ ] **Step 4: Run the runner script end-to-end (default path)**

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: scoreboard prints, `pass_rate` 1.0, all cases PASS; exits 0. No Anthropic call.

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check scripts/run_report_eval.py tests/test_graph_evals.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_report_eval.py tests/test_graph_evals.py
git commit -m "feat(graph): run report eval through the graph (compose + --llm via graph_writer)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Full verification + HANDOVER

**Files:**
- Modify: `HANDOVER.md`

**Interfaces:** none (verification + docs).

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest -q`
Expected: all prior tests (45) + the new graph tests (~14: 5 node + 7 graph + 2 through-graph eval) pass, with 1 skipped — the key-gated live LLM test. No failures.

- [ ] **Step 2: Lint the whole tree**

Run: `.venv/bin/ruff check .`
Expected: no errors.

- [ ] **Step 3: Run both eval gates through the graph**

Run: `.venv/bin/python scripts/run_watermelon_eval.py`
Expected: pass_rate 1.0, exit 0.

Run: `.venv/bin/python scripts/run_report_eval.py`
Expected: pass_rate 1.0, exit 0.

- [ ] **Step 4: Update HANDOVER.md**

In `HANDOVER.md`, update the "Where we are" section to record Stage 3 status: the three-node LangGraph graph (`sprintsight/graph/`) is built; both evals now run THROUGH the graph (watermelon 4/4 + 4/4, report 4/4) and gate CI; retrieval node does real CI-safe retrieval parked in state (not yet consumed downstream); `langgraph` added as a core dependency. Note the deferred items unchanged (chunk consumption downstream, node promotion per ADR-0001 triggers, Postgres retriever in-graph).

- [ ] **Step 5: Commit**

```bash
git add HANDOVER.md
git commit -m "docs: HANDOVER — Stage 3 LangGraph graph done; evals run through the graph

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Board (process, not code)

Per CLAUDE.md / docs/jira/workflow.md, drive the Jira board via the Composio MCP around this work:
- Before Task 1: confirm the Stage-3 Epic from `docs/jira/epic-key-map.md` and create the Stage-3 Story (do **not** set status on create); move it To Do → In Progress.
- After Task 5 verification: move the Story In Progress → In Review (evals green through the graph), then In Review → Done and post a completion comment (memory: jira-done-completion-comment). Never skip In Review; never Done on create.

## Notes for the implementer

- LangGraph node functions receive `state` as a single positional arg and return a dict of state updates; `functools.partial` is how the writer / retriever / k are injected at `build_graph` time.
- Node names (`retrieval`, `risk`, `report_writer`) deliberately differ from state keys (`retrieved`, `verdict`, `report`) — LangGraph forbids a node name colliding with a state key.
- The watermelon eval passes `inputs` without `"audience"`; `run()` defaults it to `DEFAULT_AUDIENCE`. The report node still runs for those teams (cheap, deterministic, offline) but the watermelon adapter only reads `state["verdict"]`.
- `Verdict` and `Report` are plain dataclasses, so `==` compares by field — that is what the mini-equivalence tests rely on.
- Keep the default path import-clean of `anthropic`: `make_llm_writer` is only constructed on the `--llm` branch, and it imports `anthropic` lazily inside its completer (unchanged).
```
