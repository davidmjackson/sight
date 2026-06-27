import pytest
from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

from .conftest import csrf_token


def _client():
    return TestClient(create_app())


def test_login_page_renders_form():
    resp = _client().get("/login")
    assert resp.status_code == 200
    assert 'name="email"' in resp.text
    assert 'name="password"' in resp.text


def test_login_valid_redirects_and_sets_session_cookie():
    client = _client()
    resp = client.post(
        "/login",
        data={
            "email": "admin@sprintsight.test",
            "password": "admin-watermelon",
            "csrf_token": csrf_token(client),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert "session" in resp.cookies


def test_login_wrong_password_shows_error_no_session():
    client = _client()
    resp = client.post(
        "/login",
        data={
            "email": "admin@sprintsight.test",
            "password": "wrong",
            "csrf_token": csrf_token(client),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "invalid" in resp.text.lower()
    assert "session" not in resp.cookies


def test_logout_clears_session():
    client = _client()
    client.post(
        "/login",
        data={
            "email": "admin@sprintsight.test",
            "password": "admin-watermelon",
            "csrf_token": csrf_token(client),
        },
        follow_redirects=False,
    )
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

    after = client.get("/", follow_redirects=False)
    assert after.status_code == 303
    assert after.headers["location"] == "/login"


def test_anonymous_html_redirects_to_login():
    resp = _client().get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_anonymous_team_page_redirects_to_login():
    resp = _client().get("/team/atlas", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_anonymous_api_portfolio_returns_401():
    assert _client().get("/api/portfolio").status_code == 401


def test_anonymous_api_team_returns_401():
    assert _client().get("/api/team/atlas").status_code == 401


def test_create_app_refuses_without_secret_in_non_dev(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_SECRET_KEY", raising=False)
    monkeypatch.delenv("SPRINTSIGHT_ENV", raising=False)
    with pytest.raises(RuntimeError):
        create_app()
