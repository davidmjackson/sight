from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

client = TestClient(create_app())


def test_portfolio_page_lists_all_teams():
    resp = client.get("/")
    assert resp.status_code == 200
    for team in ("Atlas", "Boreas", "Cygnus", "Draco", "Echo"):
        assert team in resp.text


def test_portfolio_page_flags_atlas():
    resp = client.get("/")
    assert "watermelon" in resp.text.lower()


def test_team_page_atlas_shows_evidence_and_signals():
    resp = client.get("/team/atlas")
    assert resp.status_code == 200
    assert "red" in resp.text.lower()
    assert "status-atlas-s15" in resp.text
    assert "burn ratio" in resp.text.lower()


def test_team_page_unknown_404():
    assert client.get("/team/nope").status_code == 404
