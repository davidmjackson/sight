from sprintsight.connect.jira_tickets import tickets_from_artifacts
from sprintsight.connect.normalize import normalize


def test_tickets_from_artifacts_pulls_key_status_team():
    # normalize renders status into the body meta line: "**Status:** In Progress · ..."
    art = normalize(
        {"key": "SSSB-1", "summary": "Login flow", "status": "In Progress",
         "team": "Atlas", "sprint": 0}
    )
    tickets = tickets_from_artifacts({art.artifact_id: art})
    assert tickets == {
        "SSSB-1": {"key": "SSSB-1", "status": "In Progress", "team": "Atlas"}
    }
