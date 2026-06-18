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
