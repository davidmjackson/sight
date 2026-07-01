from sprintsight.report.writer import compose
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


def test_team_detail_programme_report_sections_and_sources():
    d = service.team_detail("atlas", "programme")
    assert d is not None
    assert d.audience == "programme"
    assert d.report_insufficient is False
    headings = [s.heading for s in d.report_sections]
    assert "Overall status" in headings
    assert "Risks" in headings
    assert "Dependencies" in headings
    source_ids = {src.artifact_id for src in d.report_sources}
    assert "status-atlas-s15" in source_ids


def test_team_detail_exec_report_has_exec_sections_only():
    d = service.team_detail("atlas", "exec")
    headings = [s.heading for s in d.report_sections]
    assert "Top risks" in headings
    assert "Recommended next step" in headings
    assert "Sprint metrics" not in headings


def test_team_detail_team_audience_has_sprint_metrics():
    d = service.team_detail("atlas", "team")
    headings = [s.heading for s in d.report_sections]
    assert "Sprint metrics" in headings


def test_team_detail_unknown_audience_falls_back_to_programme():
    d = service.team_detail("atlas", "bogus")
    assert d.audience == "programme"


def test_team_detail_default_audience_is_programme():
    d = service.team_detail("atlas")
    assert d.audience == "programme"


def test_echo_report_is_insufficient():
    d = service.team_detail("echo")
    assert d is not None
    assert d.report_insufficient is True
    assert d.report_sections == []


def test_team_detail_programme_sections_in_profile_order():
    d = service.team_detail("atlas", "programme")
    headings = [s.heading for s in d.report_sections]
    assert headings == ["Overall status", "Risks", "Dependencies", "Milestones"]


def _real_key():
    return "sk-ant-" + "x" * 60  # 67 chars: passes the shape check


def test_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", _real_key())
    assert service._llm_enabled() is False
    assert service._active_writer() is compose


def test_llm_enabled_needs_flag_and_key(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_WEB_LLM", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", _real_key())
    assert service._llm_enabled() is True
    assert service._active_writer() is not compose


def test_llm_flag_on_but_no_key_stays_off(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_WEB_LLM", "on")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert service._llm_enabled() is False
    assert service._active_writer() is compose


def test_llm_key_present_but_flag_off_stays_off(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", _real_key())
    assert service._llm_enabled() is False


def test_llm_rejects_fake_key_shape(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_WEB_LLM", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    assert service._llm_enabled() is False


def test_report_cache_calls_writer_once_per_key(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    calls = []

    def counting(inputs):
        calls.append(inputs["audience"])
        return compose(inputs)

    monkeypatch.setattr(service, "_writer", counting)
    service.team_detail("atlas", "programme")
    service.team_detail("atlas", "programme")
    assert calls == ["programme"]  # second call served from cache


def test_report_cache_separates_audiences(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    calls = []

    def counting(inputs):
        calls.append(inputs["audience"])
        return compose(inputs)

    monkeypatch.setattr(service, "_writer", counting)
    service.team_detail("atlas", "programme")
    service.team_detail("atlas", "exec")
    assert calls == ["programme", "exec"]  # distinct keys, both computed


def test_clear_report_cache_forces_recompute(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    calls = []

    def counting(inputs):
        calls.append(inputs["audience"])
        return compose(inputs)

    monkeypatch.setattr(service, "_writer", counting)
    service.team_detail("atlas", "programme")
    service.clear_report_cache()
    service.team_detail("atlas", "programme")
    assert calls == ["programme", "programme"]


def test_offline_served_report_matches_compose(monkeypatch):
    # With the gate off, the served sections equal what compose produces directly.
    monkeypatch.delenv("SPRINTSIGHT_WEB_LLM", raising=False)
    from sprintsight.evals.fixtures import artifacts_for
    from sprintsight.report.render import heading_for

    d = service.team_detail("atlas", "programme")
    report = compose({"team": "Atlas", "audience": "programme",
                      "artifacts": artifacts_for("Atlas", [14, 15])})
    served = {s.heading: s.body for s in d.report_sections}
    expected = {heading_for(k): v for k, v in report.sections.items()}
    assert served == expected


def _summary_row(team, is_watermelon=False, has_verdict=True):
    return service.TeamRow(
        team=team,
        reported_status="green",
        actual_status="green",
        is_watermelon=is_watermelon,
        headline="",
        has_verdict=has_verdict,
    )


def test_summary_matches_seed_ground_truth():
    s = service.summarize(service.portfolio())
    assert s.teams_tracked == 5
    assert s.watermelons == 1  # Atlas
    assert s.insufficient == 1  # Echo
    assert s.sprint == 15


def test_summary_all_consistent_has_no_watermelons():
    rows = [_summary_row("A"), _summary_row("B")]
    s = service.summarize(rows)
    assert s.watermelons == 0
    assert s.teams_tracked == 2
    assert s.insufficient == 0


def test_summary_counts_insufficient_rows():
    rows = [_summary_row("A", has_verdict=False), _summary_row("B", has_verdict=False)]
    assert service.summarize(rows).insufficient == 2


def test_team_detail_atlas_has_cross_team_risk():
    d = service.team_detail("atlas")
    assert d is not None
    risk = d.cross_team_risk
    assert risk is not None
    assert risk.provider_team == "Draco"
    assert risk.dependency_ref == "DRACO-412"
    assert risk.logged_in_raid is False


def test_team_detail_boreas_has_no_cross_team_risk():
    d = service.team_detail("boreas")
    assert d is not None
    assert d.cross_team_risk is None


def test_portfolio_flags_atlas_cross_team_risk():
    atlas = _row(service.portfolio(), "Atlas")
    assert atlas.has_cross_team_risk is True


def test_portfolio_other_teams_have_no_cross_team_risk():
    rows = {r.team: r for r in service.portfolio()}
    for team in ("Boreas", "Cygnus", "Draco", "Echo"):
        assert rows[team].has_cross_team_risk is False, team
