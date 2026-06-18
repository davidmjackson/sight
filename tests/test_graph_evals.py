from sprintsight.evals.watermelon import run_watermelon_eval
from sprintsight.graph.builder import graph_detector


def test_watermelon_eval_green_through_graph():
    report = run_watermelon_eval(graph_detector())
    assert report.pass_rate == 1.0, report.summary()
