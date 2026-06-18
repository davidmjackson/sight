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
