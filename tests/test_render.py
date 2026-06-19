from sprintsight.report.contract import Report
from sprintsight.report.render import heading_for, render_report_markdown


def test_render_maps_keys_to_human_headings():
    r = Report(team="Boreas", audience="exec",
               sections={"overall_rag": "Green.", "ask": "Go."})
    md = render_report_markdown(r)
    assert "## Overall status" in md
    assert "## Recommended next step" in md
    assert "overall_rag" not in md  # raw key never shown


def test_render_covers_every_contract_key():
    # Every section key any profile can emit has a human title (no raw snake_case leaks).
    for key in ("overall_rag", "top_risks", "ask", "risks", "dependencies",
                "milestones", "sprint_metrics", "ticket_progress", "blockers"):
        assert heading_for(key) != key, f"missing human title for {key}"


def test_render_unknown_key_falls_back_to_key():
    r = Report(team="Boreas", audience="exec", sections={"weird_key": "v"})
    assert "## weird_key" in render_report_markdown(r)


def test_render_empty_sections():
    assert render_report_markdown(Report(team="Boreas", audience="exec")) == "(no sections)"
