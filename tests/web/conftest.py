import re

import pytest
from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

ADMIN = ("admin@sprintsight.test", "admin-watermelon")
MANAGER = ("manager@sprintsight.test", "manager-watermelon")
VIEWER = ("viewer@sprintsight.test", "viewer-watermelon")

_CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def csrf_token(client: TestClient) -> str:
    """Fetch the login form, extract its per-session CSRF token (also sets the session cookie)."""
    m = _CSRF_RE.search(client.get("/login").text)
    assert m, "login form is missing a csrf_token hidden field"
    return m.group(1)


def login(client: TestClient, creds: tuple[str, str]) -> TestClient:
    token = csrf_token(client)
    resp = client.post(
        "/login",
        data={"email": creds[0], "password": creds[1], "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client


@pytest.fixture
def anon_client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def client(anon_client: TestClient) -> TestClient:
    return login(anon_client, ADMIN)


@pytest.fixture
def viewer_client(anon_client: TestClient) -> TestClient:
    return login(anon_client, VIEWER)


@pytest.fixture
def manager_client(anon_client: TestClient) -> TestClient:
    return login(anon_client, MANAGER)


@pytest.fixture(autouse=True)
def _clear_report_cache():
    from sprintsight.web import service
    service.clear_report_cache()
    yield
