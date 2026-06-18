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
