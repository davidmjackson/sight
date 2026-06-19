import re

from sprintsight.report.audience import (
    MECHANICS_TERMS,
    PROFILES,
    TICKET_ID,
    contains_mechanics,
)


def test_three_locked_profiles():
    assert set(PROFILES) == {"exec", "programme", "team"}
    assert PROFILES["exec"].max_words == 150
    assert PROFILES["programme"].max_words == 400
    assert PROFILES["team"].max_words is None


def test_exec_forbids_mechanics_and_ids():
    assert PROFILES["exec"].forbid_mechanics is True
    assert PROFILES["exec"].forbid_ticket_ids is True
    assert PROFILES["team"].forbid_mechanics is False


def test_ticket_id_regex_matches_real_ids():
    assert re.search(TICKET_ID, "blocked on DRACO-412 today")
    assert not re.search(TICKET_ID, "all green, nothing to report")
    assert "velocity" in MECHANICS_TERMS


def test_contains_mechanics_flags_real_sprint_wording():
    # The mechanics sense: standalone words and the "story points" phrase.
    assert contains_mechanics("Completed 38 points this sprint.")
    assert contains_mechanics("Five story points carried over.")
    assert contains_mechanics("Velocity is steady.")
    assert contains_mechanics("The burndown is on track.")


def test_contains_mechanics_allows_unrelated_compounds():
    # The writer's own "watch-point(s)" prose and similar compounds must NOT be flagged;
    # substring matching used to reject them and force a fallback to terse compose output.
    assert not contains_mechanics("Secondary watch-points: timezone edge cases.")
    assert not contains_mechanics("Several touchpoints with the vendor remain.")
    assert not contains_mechanics("Two checkpoints before release.")
    assert not contains_mechanics("Delivery is green and on track.")
