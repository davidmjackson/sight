"""SS-2.3: the watermelon eval is wired to the corpus and bites (red until SS-2.7).

These tests assert the eval is correctly RED with no detector — keeping CI green while
proving the gate works. When SS-2.7 lands the detector, a separate test will assert green.
"""

from sprintsight.evals.watermelon import Verdict, build_cases, null_detector, run_watermelon_eval


def test_four_cases_one_per_team():
    cases = build_cases()
    assert [c.name for c in cases] == ["atlas", "boreas", "cygnus", "draco"]


def test_red_without_a_detector():
    report = run_watermelon_eval(null_detector)
    # Eval-first: with no detector the suite must not pass.
    assert report.pass_rate == 0.0
    # The evidence gate fails on all 4 cases (null detector cites nothing).
    assert report.dimension_rates()["evidence"] == (0, 4)
    # The Atlas watermelon — the case that must never be missed — is among the failures.
    assert "atlas" in report.summary()["failures"]


def test_evidence_gate_blocks_lucky_guess():
    # A detector that guesses the right labels but cites no evidence must still FAIL.
    def label_only(inputs):
        truth = {
            "Atlas": (True, "red"),
            "Boreas": (False, "green"),
            "Cygnus": (False, "amber"),
            "Draco": (False, "amber"),
        }[inputs["team"]]
        return Verdict(
            team=inputs["team"],
            reported_status="?",
            actual_status=truth[1],
            is_watermelon=truth[0],
            evidence=[],  # the lucky guess: no evidence
        )

    report = run_watermelon_eval(label_only)
    assert report.dimension_rates()["classification"] == (4, 4)  # labels right
    assert report.dimension_rates()["evidence"] == (0, 4)  # but evidence absent
    assert report.pass_rate == 0.0  # so nothing passes
