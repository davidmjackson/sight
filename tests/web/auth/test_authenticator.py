import pytest

from sprintsight.web.auth.users import SeedAuthenticator, SupabaseAuthenticator, User


def test_authenticate_valid_admin():
    auth = SeedAuthenticator()
    user = auth.authenticate("admin@sprintsight.test", "admin-watermelon")
    assert user == User(email="admin@sprintsight.test", role="admin")


def test_authenticate_is_case_insensitive_on_email():
    auth = SeedAuthenticator()
    user = auth.authenticate("Admin@Sprintsight.TEST", "admin-watermelon")
    assert user is not None
    assert user.role == "admin"


def test_authenticate_wrong_password_returns_none():
    auth = SeedAuthenticator()
    assert auth.authenticate("admin@sprintsight.test", "nope") is None


def test_authenticate_unknown_email_returns_none():
    auth = SeedAuthenticator()
    assert auth.authenticate("ghost@sprintsight.test", "admin-watermelon") is None


def test_all_users_returns_three_roles():
    auth = SeedAuthenticator()
    roles = {u.role for u in auth.all_users()}
    assert roles == {"admin", "delivery_manager", "viewer"}


def test_supabase_authenticator_is_deferred():
    with pytest.raises(NotImplementedError):
        SupabaseAuthenticator().authenticate("a@b.test", "x")
