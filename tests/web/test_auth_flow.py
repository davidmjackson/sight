from fastapi.testclient import TestClient

from sprintsight.web.app import create_app


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
        data={"email": "admin@sprintsight.test", "password": "admin-watermelon"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert "session" in resp.cookies


def test_login_wrong_password_shows_error_no_session():
    client = _client()
    resp = client.post(
        "/login",
        data={"email": "admin@sprintsight.test", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "invalid" in resp.text.lower()
    assert "session" not in resp.cookies


def test_logout_clears_session():
    client = _client()
    client.post(
        "/login",
        data={"email": "admin@sprintsight.test", "password": "admin-watermelon"},
        follow_redirects=False,
    )
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
