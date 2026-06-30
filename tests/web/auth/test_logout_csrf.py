"""Logout CSRF protection (synchronizer token). Eval-first.

Sign-out must be a state-changing POST, not a GET, and must carry the per-session
CSRF token. A forged cross-site request (no token / wrong token / GET) must NOT log
the user out: the slice fails closed, leaving the session intact.
"""

import re

from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

ADMIN = {"email": "admin@sprintsight.test", "password": "admin-watermelon"}
_LOGIN_TOKEN_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
# The logout form's hidden token, scoped to the sign-out form so we read the real thing.
_LOGOUT_TOKEN_RE = re.compile(
    r'<form[^>]*action="/logout".*?name="csrf_token" value="([^"]+)"', re.S
)


def _login() -> TestClient:
    client = TestClient(create_app())
    m = _LOGIN_TOKEN_RE.search(client.get("/login").text)
    assert m, "login form is missing a csrf_token hidden field"
    resp = client.post(
        "/login", data={**ADMIN, "csrf_token": m.group(1)}, follow_redirects=False
    )
    assert resp.status_code == 303
    return client


def _logged_in(client: TestClient) -> bool:
    """True iff the session still authenticates (the portfolio serves rather than redirects)."""
    return client.get("/", follow_redirects=False).status_code == 200


def test_authenticated_page_renders_a_logout_post_form_with_token():
    client = _login()
    html = client.get("/").text
    m = _LOGOUT_TOKEN_RE.search(html)
    assert m, "authenticated shell is missing a POST /logout form with a csrf_token"
    assert m.group(1)  # non-empty token


def test_logout_get_is_not_allowed():
    """GET /logout must no longer be a thing — a link/<img> cannot trigger sign-out."""
    client = _login()
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 405
    assert _logged_in(client)  # still signed in


def test_logout_without_token_is_rejected():
    client = _login()
    resp = client.post("/logout", data={}, follow_redirects=False)
    assert resp.status_code == 400
    assert _logged_in(client)  # forged logout did nothing


def test_logout_with_wrong_token_is_rejected():
    client = _login()
    resp = client.post(
        "/logout", data={"csrf_token": "not-the-real-token"}, follow_redirects=False
    )
    assert resp.status_code == 400
    assert _logged_in(client)


def test_logout_with_valid_token_signs_out():
    client = _login()
    m = _LOGOUT_TOKEN_RE.search(client.get("/").text)
    assert m
    resp = client.post(
        "/logout", data={"csrf_token": m.group(1)}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    assert not _logged_in(client)  # session cleared


def test_logout_token_is_tied_to_its_own_session():
    """Another session's valid token must not log this session out."""
    other = TestClient(create_app())
    m_other = _LOGIN_TOKEN_RE.search(other.get("/login").text)
    assert m_other
    foreign_token = m_other.group(1)

    client = _login()
    resp = client.post(
        "/logout", data={"csrf_token": foreign_token}, follow_redirects=False
    )
    assert resp.status_code == 400
    assert _logged_in(client)  # a foreign token is not valid here


def test_logout_non_ascii_token_rejected_cleanly():
    """A non-ASCII forged token must fail closed as 400, not crash with a 500."""
    client = _login()
    resp = client.post(
        "/logout", data={"csrf_token": "é-forged-tøken"}, follow_redirects=False
    )
    assert resp.status_code == 400
    assert _logged_in(client)
