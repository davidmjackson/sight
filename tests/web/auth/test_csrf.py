"""Slice 5 — login CSRF protection (synchronizer token). Eval-first.

The login form must plant a per-session token; POST /login must reject any submission whose token
is missing, wrong, or from a different session, and must do so BEFORE checking the password.
"""

import re

from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

ADMIN = {"email": "admin@sprintsight.test", "password": "admin-watermelon"}
_TOKEN_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def _client() -> TestClient:
    return TestClient(create_app())


def _token(client: TestClient) -> str:
    html = client.get("/login").text
    m = _TOKEN_RE.search(html)
    assert m, "login form is missing a csrf_token hidden field"
    return m.group(1)


def test_login_form_renders_a_csrf_token():
    assert _token(_client())  # non-empty


def test_login_without_token_is_rejected():
    client = _client()
    client.get("/login")  # establish a session (with a token) first
    resp = client.post("/login", data=ADMIN, follow_redirects=False)
    assert resp.status_code == 400
    assert "session" not in resp.cookies  # not logged in


def test_login_with_wrong_token_is_rejected():
    client = _client()
    client.get("/login")
    resp = client.post(
        "/login", data={**ADMIN, "csrf_token": "not-the-real-token"}, follow_redirects=False
    )
    assert resp.status_code == 400
    assert "session" not in resp.cookies


def test_login_with_valid_token_succeeds():
    client = _client()
    token = _token(client)
    resp = client.post(
        "/login", data={**ADMIN, "csrf_token": token}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_token_is_tied_to_its_own_session():
    a = _client()
    token_a = _token(a)
    b = _client()
    b.get("/login")  # b gets its own, different session token
    resp = b.post(
        "/login", data={**ADMIN, "csrf_token": token_a}, follow_redirects=False
    )
    assert resp.status_code == 400  # a's token is not valid in b's session


def test_non_ascii_token_rejected_cleanly():
    """A non-ASCII forged token must fail closed as 400, not crash with a 500."""
    client = _client()
    client.get("/login")
    resp = client.post(
        "/login", data={**ADMIN, "csrf_token": "é-forged-tøken"}, follow_redirects=False
    )
    assert resp.status_code == 400


def test_csrf_checked_before_password():
    """A bad token with a WRONG password still fails as CSRF (400), not as auth (200)."""
    client = _client()
    client.get("/login")
    resp = client.post(
        "/login",
        data={"email": ADMIN["email"], "password": "wrong", "csrf_token": "bogus"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
