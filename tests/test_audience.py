import re

from sprintsight.report.audience import MECHANICS_TERMS, PROFILES, TICKET_ID


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
