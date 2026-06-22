import pytest
from fastapi.testclient import TestClient

from sprintsight.web.app import create_app

ADMIN = ("admin@sprintsight.test", "admin-watermelon")
MANAGER = ("manager@sprintsight.test", "manager-watermelon")
VIEWER = ("viewer@sprintsight.test", "viewer-watermelon")


def login(client: TestClient, creds: tuple[str, str]) -> TestClient:
    resp = client.post(
        "/login",
        data={"email": creds[0], "password": creds[1]},
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
