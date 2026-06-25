import json
from pathlib import Path

from sprintsight.connect.github import RecordedGitHubConnector
from sprintsight.crosstool import reconcile

_DATA = Path(__file__).resolve().parents[2] / "data" / "captured"
AS_OF = "2026-06-25T00:00:00Z"


def _verdicts() -> dict:
    tickets = json.loads((_DATA / "crosstool_web_jira.json").read_text(encoding="utf-8"))
    activity = RecordedGitHubConnector.from_file(
        _DATA / "crosstool_web_github.json"
    ).fetch_activity()
    return {
        t["key"]: reconcile(
            {"ticket": t, "activity": activity.get(t["key"]), "as_of": AS_OF}
        )
        for t in tickets
    }


def test_web_fixtures_show_all_three_colours():
    v = _verdicts()
    assert v["SSSB-1"].is_watermelon                       # In Progress, no linked work
    assert v["SSSB-2"].is_watermelon                       # Done, PR open-unmerged
    assert v["SSSB-3"].actual_status == "green"
    assert not v["SSSB-3"].is_watermelon                   # Done, PR merged -> clean
    assert v["SSSB-7"].actual_status == "amber"            # In Progress, PR stalled
