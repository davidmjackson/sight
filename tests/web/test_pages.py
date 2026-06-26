from sprintsight.web import crosstool_service


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


def test_login_page_uses_shell(anon_client):
    html = anon_client.get("/login").text
    assert "app-header" in html  # inherits the branded shell
    assert "brand-logo" in html


def test_admin_accounts_uses_shell(client):
    html = client.get("/admin/accounts").text
    assert "app-header" in html
    assert "Accounts" in html


def test_crosstool_page_renders_summary_and_flags(client):
    html = client.get("/crosstool").text
    assert "summary-band" in html
    assert "SSSB-1" in html                     # a watermelon ticket
    assert "SSSB-7" in html                     # the stalled ticket
    assert "no activity" in html                # the stalled citation
    assert "Jira SSSB-1" in html                # both tools cited
    assert "GitHub:" in html


def test_crosstool_api_returns_counts(client):
    body = client.get("/api/crosstool").json()
    assert body["summary"]["watermelons"] == 2
    assert body["summary"]["stalled"] == 1
    assert len(body["rows"]) == 4


def test_crosstool_requires_login(anon_client):
    resp = anon_client.get("/crosstool", follow_redirects=False)
    assert resp.status_code == 303              # redirected to /login


def test_portfolio_links_to_crosstool(client):
    assert "/crosstool" in client.get("/").text


def test_crosstool_page_shows_offline_badge_by_default(client):
    resp = client.get("/crosstool")
    assert resp.status_code == 200
    assert "offline replay" in resp.text


def test_crosstool_page_shows_live_badge(client, monkeypatch):
    """Live gate open + fake live source -> page renders the live-as-of badge."""
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_LIVE", "on")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("COMPOSIO_API_KEY", "x")
    monkeypatch.setenv("COMPOSIO_CONNECTED_ACCOUNT_ID", "ac_x")
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_REPO", "owner/repo")
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_PROJECT", "SSSB")

    def _fake_live_source():
        return (
            [{"key": "SSSB-1", "status": "In Progress", "team": "Atlas"}],
            {},
            "2026-07-01T12:00:00Z",
            "live",
        )

    monkeypatch.setattr(crosstool_service, "_live_source", _fake_live_source)
    resp = client.get("/crosstool")
    assert resp.status_code == 200
    assert "live as of 2026-07-01T12:00:00Z" in resp.text


def test_crosstool_page_shows_offline_failed_badge(client, monkeypatch):
    """Live gate open but live source raises -> page renders the offline-failed badge."""
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_LIVE", "on")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("COMPOSIO_API_KEY", "x")
    monkeypatch.setenv("COMPOSIO_CONNECTED_ACCOUNT_ID", "ac_x")
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_REPO", "owner/repo")
    monkeypatch.setenv("SPRINTSIGHT_CROSSTOOL_PROJECT", "SSSB")

    def _failing_live_source():
        raise RuntimeError("network down")

    monkeypatch.setattr(crosstool_service, "_live_source", _failing_live_source)
    resp = client.get("/crosstool")
    assert resp.status_code == 200
    assert "offline (live read failed)" in resp.text
