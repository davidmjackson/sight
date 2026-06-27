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
