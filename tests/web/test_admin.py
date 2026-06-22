def test_admin_sees_accounts_list(client):
    resp = client.get("/admin/accounts")
    assert resp.status_code == 200
    assert "admin@sprintsight.test" in resp.text
    assert "viewer@sprintsight.test" in resp.text
    assert "delivery_manager" in resp.text


def test_admin_page_leaks_no_hashes(client):
    resp = client.get("/admin/accounts")
    assert "salt" not in resp.text.lower()
    assert "hash" not in resp.text.lower()


def test_viewer_forbidden(viewer_client):
    assert viewer_client.get("/admin/accounts").status_code == 403


def test_manager_forbidden(manager_client):
    assert manager_client.get("/admin/accounts").status_code == 403


def test_anonymous_admin_redirects_to_login(anon_client):
    resp = anon_client.get("/admin/accounts", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
