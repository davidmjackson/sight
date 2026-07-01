from dataclasses import replace

from sprintsight.crossteam import CrossTeamRisk, reconcile_cross_team
from sprintsight.evals.fixtures import artifacts_for

SPRINTS = [14, 15]


def _provider():
    """Real corpus provider loader, case-insensitive by team name."""
    return lambda team: artifacts_for(team, SPRINTS)


def test_atlas_draco_slip_is_reconciled():
    risk = reconcile_cross_team("Atlas", artifacts_for("Atlas", SPRINTS), _provider())
    assert isinstance(risk, CrossTeamRisk)
    assert risk.consumer_team == "Atlas"
    assert risk.provider_team == "Draco"
    assert risk.dependency_ref == "DRACO-412"
    assert "Auth API" in risk.dependency_label
    assert risk.consumer_citation == "slack-atlas-s15-msg-dep"
    assert "jira-draco-s15-authapi" in risk.provider_citations
    # Behaviour 3: the dependency is NOT in Atlas's RAID -> recommend logging it.
    assert risk.logged_in_raid is False
    # Headline names BOTH teams and the slip.
    assert "Atlas" in risk.headline and "Draco" in risk.headline
    assert "sprint 16" in risk.headline.lower()


def test_boreas_has_no_cross_team_risk():
    risk = reconcile_cross_team("Boreas", artifacts_for("Boreas", SPRINTS), _provider())
    assert risk is None


def test_does_not_cry_wolf_when_provider_not_slipping():
    """If the named provider ticket is NOT slipping, there is no risk."""
    atlas = artifacts_for("Atlas", SPRINTS)
    draco = artifacts_for("Draco", SPRINTS)
    # Patch the Draco ticket body to a delivered/on-time state (no slip language).
    tid = "jira-draco-s15-authapi"
    draco[tid] = replace(
        draco[tid],
        body="| Summary | Draco Auth API v2 |\n| Status | Done |\nDelivered on time in Sprint 15.",
    )

    def provider(team):
        return draco if team.lower() == "draco" else artifacts_for(team, SPRINTS)

    assert reconcile_cross_team("Atlas", atlas, provider) is None


def test_logged_in_raid_when_dependency_is_recorded():
    """If Atlas HAS logged the ref in its RAID, logged_in_raid is True (no 'recommend logging')."""
    atlas = artifacts_for("Atlas", SPRINTS)
    raid_id = "raid-atlas-s15"
    atlas[raid_id] = replace(
        atlas[raid_id],
        body=atlas[raid_id].body + "\n| R-ATLAS-99 | DRACO-412 auth API slip | owner: Priya |",
    )
    risk = reconcile_cross_team("Atlas", atlas, _provider())
    assert risk is not None
    assert risk.logged_in_raid is True
