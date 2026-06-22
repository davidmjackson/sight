def test_portfolio_page_lists_all_teams(client):
    resp = client.get("/")
    assert resp.status_code == 200
    for team in ("Atlas", "Boreas", "Cygnus", "Draco", "Echo"):
        assert team in resp.text


def test_portfolio_page_flags_atlas(client):
    resp = client.get("/")
    assert "watermelon" in resp.text.lower()


def test_team_page_atlas_shows_evidence_and_signals(client):
    resp = client.get("/team/atlas")
    assert resp.status_code == 200
    assert "red" in resp.text.lower()
    assert "status-atlas-s15" in resp.text
    assert "burn ratio" in resp.text.lower()


def test_team_page_unknown_404(client):
    assert client.get("/team/nope").status_code == 404


def test_team_page_shows_report_and_audience_switch(client):
    html = client.get("/team/atlas").text
    assert "Status report" in html
    assert "?audience=exec" in html
    assert "?audience=programme" in html
    assert "?audience=team" in html
    assert "Risks" in html  # programme default section heading


def test_team_page_exec_audience_renders_exec_section(client):
    html = client.get("/team/atlas?audience=exec").text
    assert "Recommended next step" in html


def test_shell_has_branded_header(client):
    html = client.get("/").text
    assert "app-header" in html
    assert "brand-logo" in html


def test_portfolio_page_shows_summary_band(client):
    html = client.get("/").text
    assert "summary-band" in html
    assert "Watermelon" in html  # KPI label
    assert "Teams tracked" in html


def test_team_page_atlas_has_verdict_banner(client):
    html = client.get("/team/atlas").text
    assert "verdict-banner" in html
    assert "verdict-emoji" in html


def test_team_page_audience_tabs_present(client):
    html = client.get("/team/atlas").text
    assert "audience-tabs" in html
    assert html.count('class="aud') >= 3  # three audience tabs
