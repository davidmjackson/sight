"""Real Supabase Auth wiring — eval-first, fully offline (the network call is faked).

Pins: the pure response->User mappers (role comes ONLY from app_metadata; a self-set
user_metadata role is ignored -> viewer; missing email -> None), authenticate() orchestration with
a faked password grant, and the fail-safe factory/gate (SeedAuthenticator by default).
"""


from sprintsight.web.auth.users import (
    SeedAuthenticator,
    SupabaseAuthenticator,
    User,
    _role_from,
    _supabase_configured,
    _user_from_auth,
    make_authenticator,
)

# --- pure mappers ---------------------------------------------------------------

def test_role_from_app_metadata():
    assert _role_from({"app_metadata": {"role": "admin"}}) == "admin"


def test_role_defaults_to_viewer_when_absent():
    assert _role_from({"app_metadata": {}}) == "viewer"
    assert _role_from({}) == "viewer"


def test_role_ignores_self_set_user_metadata():
    """SECURITY: user_metadata is user-editable, so a role there must NOT be honored."""
    user = {"user_metadata": {"role": "admin"}, "app_metadata": {}}
    assert _role_from(user) == "viewer"


def test_role_rejects_unknown_value():
    assert _role_from({"app_metadata": {"role": "superuser"}}) == "viewer"


def test_user_from_auth_maps_email_and_role():
    data = {"user": {"email": "a@b.test", "app_metadata": {"role": "delivery_manager"}}}
    u = _user_from_auth(data)
    assert u == User(email="a@b.test", role="delivery_manager")


def test_user_from_auth_none_without_email():
    assert _user_from_auth({"user": {"app_metadata": {"role": "admin"}}}) is None
    assert _user_from_auth({}) is None


def test_user_from_auth_fails_closed_on_non_dict_shapes():
    # a malformed 200 body must fail closed, not raise (-> a 500 on /login)
    assert _user_from_auth([]) is None
    assert _user_from_auth("x") is None
    assert _user_from_auth({"user": []}) is None


# --- authenticate() orchestration (network faked) -------------------------------

def test_authenticate_returns_user_on_success(monkeypatch):
    # patch at the class (the dataclass is frozen, so instance attrs can't be set)
    monkeypatch.setattr(
        SupabaseAuthenticator, "_password_grant",
        lambda self, email, password: {
            "user": {"email": email, "app_metadata": {"role": "viewer"}}
        },
    )
    auth = SupabaseAuthenticator("https://x.supabase.co", "anon")
    assert auth.authenticate("u@b.test", "pw") == User(email="u@b.test", role="viewer")


def test_authenticate_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(
        SupabaseAuthenticator, "_password_grant", lambda self, email, password: None
    )
    auth = SupabaseAuthenticator("https://x.supabase.co", "anon")
    assert auth.authenticate("u@b.test", "wrong") is None


def test_supabase_all_users_is_empty():
    assert SupabaseAuthenticator("https://x.supabase.co", "anon").all_users() == []


# --- _password_grant network branches (httpx faked, no real network) ------------

class _Resp:
    def __init__(self, status_code, payload=None, raises=False):
        self.status_code = status_code
        self._payload = payload
        self._raises = raises

    def json(self):
        if self._raises:
            raise ValueError("no json body")
        return self._payload


def _auth():
    return SupabaseAuthenticator("https://x.supabase.co/", "anon")


def test_password_grant_success_returns_body(monkeypatch):
    import httpx
    body = {"user": {"email": "a@b.test"}}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(200, body))
    assert _auth()._password_grant("a@b.test", "pw") == body


def test_password_grant_non_200_returns_none(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(400, {"error": "bad"}))
    assert _auth()._password_grant("a@b.test", "wrong") is None


def test_password_grant_network_error_returns_none(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(httpx, "post", boom)
    assert _auth()._password_grant("a@b.test", "pw") is None


def test_password_grant_non_json_returns_none(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(200, raises=True))
    assert _auth()._password_grant("a@b.test", "pw") is None


# --- fail-safe factory / gate ---------------------------------------------------

def _clear(monkeypatch):
    for k in ("SPRINTSIGHT_AUTH", "SUPABASE_URL", "SUPABASE_ANON_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_default_is_seed_authenticator(monkeypatch):
    _clear(monkeypatch)
    assert _supabase_configured() is False
    assert isinstance(make_authenticator(), SeedAuthenticator)


def test_flag_without_keys_stays_seed(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SPRINTSIGHT_AUTH", "supabase")
    assert _supabase_configured() is False
    assert isinstance(make_authenticator(), SeedAuthenticator)


def test_supabase_selected_with_flag_and_keys(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SPRINTSIGHT_AUTH", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    assert _supabase_configured() is True
    assert isinstance(make_authenticator(), SupabaseAuthenticator)
