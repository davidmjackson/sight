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
