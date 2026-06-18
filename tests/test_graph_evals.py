from sprintsight.evals.report import run_report_eval
from sprintsight.evals.watermelon import run_watermelon_eval
from sprintsight.graph.builder import graph_detector, graph_writer
from sprintsight.report.writer import compose


def test_watermelon_eval_green_through_graph():
    report = run_watermelon_eval(graph_detector())
    assert report.pass_rate == 1.0, report.summary()


def test_report_eval_green_through_graph():
    report = run_report_eval(graph_writer(compose))
    assert report.pass_rate == 1.0, report.summary()
