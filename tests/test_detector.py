"""SS-2.7: the baseline detector turns the watermelon eval GREEN (4/4 + 4/4)."""

from sprintsight.detector import detect, parse_metrics, parse_reported_status
from sprintsight.evals.fixtures import artifacts_for
from sprintsight.evals.watermelon import run_watermelon_eval


def test_eval_is_green_with_detector():
    report = run_watermelon_eval(detect)
    assert report.pass_rate == 1.0  # all 4 cases pass both gates
    assert report.dimension_rates()["classification"] == (4, 4)
    assert report.dimension_rates()["evidence"] == (4, 4)


def test_atlas_is_the_watermelon():
    verdict = detect({"team": "Atlas", "artifacts": artifacts_for("Atlas", [14, 15])})
    assert verdict.is_watermelon is True
    assert verdict.reported_status == "green"
    assert verdict.actual_status == "red"
    # cites the hidden dependency chat that the RAID omits
    assert "slack-atlas-s15-msg-dep" in verdict.evidence


def test_draco_near_miss_not_watermelon():
    verdict = detect({"team": "Draco", "artifacts": artifacts_for("Draco", [14, 15])})
    assert verdict.is_watermelon is False
    assert verdict.actual_status == "amber"  # bug spike triaged -> not escalated to red
    assert {"bugspike-draco-s15", "triage-draco-s15"} <= set(verdict.evidence)


def test_metric_parsing_tolerates_formats():
    # Pipe-, table-, and dot-separated burndowns all parse.
    pipe = (
        "**Committed:** 40 points | **Completed:** 38 points | "
        "**Carry-over:** 1 story | **Velocity:** 38"
    )
    table = (
        "| Committed points | 32 |\n| Completed points | 25 |\n"
        "| Carry-over stories | 3 |\n| Velocity | 25 |"
    )
    m1 = parse_metrics(pipe)
    m2 = parse_metrics(table)
    assert (m1.committed, m1.completed, m1.carry_over, m1.velocity) == (40, 38, 1, 38)
    assert (m2.committed, m2.completed, m2.carry_over, m2.velocity) == (32, 25, 3, 25)


def test_reported_status_parsing():
    assert parse_reported_status("**Overall status: 🟢 GREEN — on track**") == "green"
    assert parse_reported_status("**Overall status: AMBER**") == "amber"
