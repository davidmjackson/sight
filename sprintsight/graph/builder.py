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
from langgraph.graph.state import CompiledStateGraph

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
) -> CompiledStateGraph:
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
    # nodes fill retrieved/verdict/report; GraphState is total=False so a partial init is valid.
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
