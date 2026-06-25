"""Goal B cross-tool watermelon eval: RED until reconcile() exists, then GREEN."""

from sprintsight.evals.crosstool_eval import null_reconciler, run_cross_tool_eval


def test_red_without_a_reconciler():
    report = run_cross_tool_eval(null_reconciler)
    assert report.pass_rate == 0.0
    # The two true watermelons must be among the failures while abstaining.
    assert {"case1", "case2"} <= set(report.summary()["failures"])
