def test_api_portfolio_verdicts(client):
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    rows = {row["team"]: row for row in resp.json()}
    assert rows["Atlas"]["is_watermelon"] is True
    assert rows["Atlas"]["actual_status"] == "red"
    assert rows["Boreas"]["is_watermelon"] is False
    assert rows["Echo"]["has_verdict"] is False


def test_api_team_atlas_detail(client):
    resp = client.get("/api/team/atlas")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_watermelon"] is True
    ids = {e["artifact_id"] for e in body["evidence"]}
    assert "slack-atlas-s15-msg-dep" in ids
    assert body["signals"]


def test_api_team_unknown_404(client):
    assert client.get("/api/team/nope").status_code == 404


def test_api_team_audience_param_selects_exec(client):
    body = client.get("/api/team/atlas?audience=exec").json()
    assert body["audience"] == "exec"
    headings = {s["heading"] for s in body["report_sections"]}
    assert "Recommended next step" in headings
    assert "Sprint metrics" not in headings


def test_api_team_default_audience_is_programme(client):
    body = client.get("/api/team/atlas").json()
    assert body["audience"] == "programme"
    headings = {s["heading"] for s in body["report_sections"]}
    assert "Risks" in headings
    assert {src["artifact_id"] for src in body["report_sources"]}


def test_api_team_unknown_audience_falls_back(client):
    body = client.get("/api/team/atlas?audience=bogus").json()
    assert body["audience"] == "programme"


def test_api_echo_report_insufficient(client):
    body = client.get("/api/team/echo").json()
    assert body["report_insufficient"] is True
    assert body["report_sections"] == []
