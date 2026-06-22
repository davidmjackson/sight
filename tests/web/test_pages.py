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
