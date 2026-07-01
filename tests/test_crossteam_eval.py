"""Deterministic moat gate: the reconciler must reproduce the authored dependency_thread
(Atlas depends on Draco's DRACO-412 auth API, slipped, unlogged in Atlas's RAID)."""

from sprintsight.crossteam import reconcile_cross_team
from sprintsight.evals.fixtures import artifacts_for, load_ground_truth

SPRINTS = [14, 15]


def test_reconciler_matches_ground_truth_dependency_thread():
    thread = load_ground_truth()["dependency_thread"]
    consumer = thread["consumer_team"]
    risk = reconcile_cross_team(
        consumer,
        artifacts_for(consumer, SPRINTS),
        lambda team: artifacts_for(team, SPRINTS),
    )
    assert risk is not None
    assert risk.provider_team == thread["provider_team"]
    assert risk.dependency_ref == thread["provider_ticket"]
    assert risk.consumer_citation == thread["raised_in"]
    # It reconciles from the provider's own ticket.
    assert thread["reconcilable_from"][0] in risk.provider_citations
    # The authored truth says it is missing from Atlas's RAID -> we recommend logging it.
    assert "raid-atlas-s15" in thread["missing_from"]
    assert risk.logged_in_raid is False
