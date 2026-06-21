from sprintsight.web import service


def _row(rows, team):
    return next(r for r in rows if r.team == team)


def test_portfolio_returns_all_teams():
    rows = service.portfolio()
    assert {r.team for r in rows} == {"Atlas", "Boreas", "Cygnus", "Draco", "Echo"}


def test_atlas_is_watermelon_red():
    atlas = _row(service.portfolio(), "Atlas")
    assert atlas.has_verdict is True
    assert atlas.is_watermelon is True
    assert atlas.reported_status == "green"
    assert atlas.actual_status == "red"


def test_boreas_green_not_watermelon():
    boreas = _row(service.portfolio(), "Boreas")
    assert boreas.has_verdict is True
    assert boreas.is_watermelon is False
    assert boreas.actual_status == "green"


def test_cygnus_amber_not_watermelon():
    cygnus = _row(service.portfolio(), "Cygnus")
    assert cygnus.is_watermelon is False
    assert cygnus.actual_status == "amber"


def test_draco_amber_not_watermelon():
    draco = _row(service.portfolio(), "Draco")
    assert draco.is_watermelon is False
    assert draco.actual_status == "amber"


def test_echo_insufficient_evidence():
    echo = _row(service.portfolio(), "Echo")
    assert echo.has_verdict is False
    assert echo.is_watermelon is False


def test_team_detail_atlas_evidence_and_signals():
    detail = service.team_detail("atlas")
    assert detail is not None
    assert detail.is_watermelon is True
    ids = {e.artifact_id for e in detail.evidence}
    assert "status-atlas-s15" in ids
    assert "burndown-atlas-s15" in ids
    assert "slack-atlas-s15-msg-dep" in ids
    assert detail.signals, "expected non-empty signals"
    assert any("burn ratio" in s for s in detail.signals)


def test_team_detail_unknown_returns_none():
    assert service.team_detail("nope") is None


def test_team_detail_echo_insufficient():
    detail = service.team_detail("echo")
    assert detail is not None
    assert detail.has_verdict is False
    assert detail.evidence == []
