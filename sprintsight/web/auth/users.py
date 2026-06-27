"""User model + Authenticator seam for the offline auth stand-in (SS-34).

SeedAuthenticator validates credentials against a checked-in YAML of synthetic
demo users (passwords stored hashed). SupabaseAuthenticator is the deferred real
provider behind the same interface (ADR-0002); wiring it later touches only this
edge, not the web app.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml

from sprintsight.web.auth.hashing import verify_password

ROLES = ("admin", "delivery_manager", "viewer")
_SEED_FILE = Path(__file__).resolve().parent / "seed_users.yaml"


@dataclass(frozen=True)
class User:
    email: str
    role: str


class Authenticator(Protocol):
    def authenticate(self, email: str, password: str) -> User | None: ...
    def all_users(self) -> list[User]: ...


@dataclass(frozen=True)
class _SeedRecord:
    email: str
    role: str
    salt: str
    hash: str


class SeedAuthenticator:
    """Offline stand-in: checks credentials against the seed YAML."""

    def __init__(self, seed_file: Path = _SEED_FILE) -> None:
        raw = yaml.safe_load(seed_file.read_text()) or []
        self._records: dict[str, _SeedRecord] = {
            r["email"].lower(): _SeedRecord(
                email=r["email"], role=r["role"], salt=r["salt"], hash=r["hash"]
            )
            for r in raw
        }

    def authenticate(self, email: str, password: str) -> User | None:
        rec = self._records.get(email.strip().lower())
        if rec is None:
            return None
        if not verify_password(password, rec.salt, rec.hash):
            return None
        return User(email=rec.email, role=rec.role)

    def all_users(self) -> list[User]:
        return [User(email=r.email, role=r.role) for r in self._records.values()]


def _role_from(user: dict) -> str:
    """Resolve the app role from a Supabase user. SECURITY: read ONLY app_metadata (admin-set);
    user_metadata is user-editable, so honoring a role there would let a user self-escalate.
    Unknown/absent -> the least-privileged role."""
    role = (user.get("app_metadata") or {}).get("role")
    return role if role in ROLES else "viewer"


def _user_from_auth(data: dict) -> User | None:
    """Pure map of a GoTrue token response to our User, or None if there is no email."""
    user = data.get("user") or {}
    email = user.get("email")
    if not email:
        return None
    return User(email=email, role=_role_from(user))


@dataclass(frozen=True)
class SupabaseAuthenticator:
    """Verifies credentials against Supabase Auth (GoTrue) via the anon password grant, returning
    our User. The network call is walled off in `_password_grant`; everything else is pure and
    fails closed. We do not store the Supabase JWT — the app keeps its own signed session."""

    base_url: str
    anon_key: str

    def authenticate(self, email: str, password: str) -> User | None:
        data = self._password_grant(email, password)
        if data is None:
            return None
        return _user_from_auth(data)

    def all_users(self) -> list[User]:
        # Accounts are managed in Supabase; admin-listing via the admin API is deferred.
        return []

    def _password_grant(self, email: str, password: str) -> dict | None:
        """The ONLY network call: POST the GoTrue password grant with the anon key. Returns the
        parsed JSON on 200, else None (bad creds / unconfirmed / error) so login fails closed."""
        import httpx  # lazy: only when a real Supabase login is attempted

        url = self.base_url.rstrip("/") + "/auth/v1/token?grant_type=password"
        try:
            resp = httpx.post(
                url,
                headers={"apikey": self.anon_key, "Content-Type": "application/json"},
                json={"email": email, "password": password},
                timeout=10.0,
            )
        except Exception:
            logging.exception("Supabase auth request failed")
            return None
        if resp.status_code != 200:
            return None
        try:
            return resp.json()
        except ValueError:
            return None


_AUTH_FLAG = "SPRINTSIGHT_AUTH"


def _supabase_configured() -> bool:
    """True only when Supabase auth is selected AND its creds are present (fail-safe)."""
    return (
        os.getenv(_AUTH_FLAG) == "supabase"
        and bool(os.getenv("SUPABASE_URL"))
        and bool(os.getenv("SUPABASE_ANON_KEY"))
    )


def make_authenticator() -> Authenticator:
    """The active authenticator: Supabase when gated on, else the offline seed default."""
    if _supabase_configured():
        return SupabaseAuthenticator(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    return SeedAuthenticator()
