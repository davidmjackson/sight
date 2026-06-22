import pytest
from fastapi import HTTPException

from sprintsight.web.auth.session import (
    login_session,
    logout_session,
    require_api_user,
    session_secret,
    session_user,
)
from sprintsight.web.auth.users import User


class FakeRequest:
    def __init__(self, session=None):
        self.session = session if session is not None else {}


def test_login_then_read_round_trips_user():
    req = FakeRequest()
    login_session(req, User(email="a@b.test", role="viewer"))
    user = session_user(req)
    assert user == User(email="a@b.test", role="viewer")


def test_logout_clears_user():
    req = FakeRequest()
    login_session(req, User(email="a@b.test", role="admin"))
    logout_session(req)
    assert session_user(req) is None


def test_session_user_none_when_empty():
    assert session_user(FakeRequest()) is None


def test_session_user_none_when_garbled():
    assert session_user(FakeRequest({"user": {"email": "a@b.test"}})) is None


def test_require_api_user_raises_401_when_anonymous():
    with pytest.raises(HTTPException) as exc:
        require_api_user(FakeRequest())
    assert exc.value.status_code == 401


def test_require_api_user_returns_user_when_present():
    req = FakeRequest()
    login_session(req, User(email="a@b.test", role="admin"))
    assert require_api_user(req).role == "admin"


def test_session_secret_prefers_env(monkeypatch):
    monkeypatch.setenv("SPRINTSIGHT_SECRET_KEY", "from-env")
    assert session_secret() == "from-env"


def test_session_secret_falls_back_to_dev_default(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_SECRET_KEY", raising=False)
    monkeypatch.setenv("SPRINTSIGHT_ENV", "dev")
    assert session_secret() != ""


def test_session_secret_raises_without_secret_in_non_dev(monkeypatch):
    monkeypatch.delenv("SPRINTSIGHT_SECRET_KEY", raising=False)
    monkeypatch.delenv("SPRINTSIGHT_ENV", raising=False)
    with pytest.raises(RuntimeError):
        session_secret()
