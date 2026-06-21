from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

client = TestClient(create_app())


def test_api_portfolio_verdicts():
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    rows = {row["team"]: row for row in resp.json()}
    assert rows["Atlas"]["is_watermelon"] is True
    assert rows["Atlas"]["actual_status"] == "red"
    assert rows["Boreas"]["is_watermelon"] is False
    assert rows["Echo"]["has_verdict"] is False


def test_api_team_atlas_detail():
    resp = client.get("/api/team/atlas")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_watermelon"] is True
    ids = {e["artifact_id"] for e in body["evidence"]}
    assert "slack-atlas-s15-msg-dep" in ids
    assert body["signals"]


def test_api_team_unknown_404():
    assert client.get("/api/team/nope").status_code == 404
