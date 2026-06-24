"""Stage 7: the seed-board builder is pure and deterministic (no Jira calls)."""

from scripts.seed_demo_board import build_issue_specs


def test_build_issue_specs_covers_teams_and_sprints():
    specs = build_issue_specs()
    assert len(specs) >= 6
    teams = {s["team"] for s in specs}
    assert {"Atlas", "Boreas"} <= teams
    assert {15} <= {s["sprint"] for s in specs}


def test_every_spec_has_team_label_and_points():
    for s in build_issue_specs():
        assert any(lbl == f"team:{s['team'].lower()}" for lbl in s["labels"])
        assert isinstance(s["story_points"], int)


def test_atlas_dependency_signal_is_seeded():
    specs = build_issue_specs()
    atlas_text = " ".join(
        " ".join(s["comments"]) + " " + s["description"]
        for s in specs
        if s["team"] == "Atlas"
    )
    assert "Draco" in atlas_text  # the cross-team dependency phrase is present to grade against
