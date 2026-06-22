"""User model + Authenticator seam for the offline auth stand-in (SS-34).

SeedAuthenticator validates credentials against a checked-in YAML of synthetic
demo users (passwords stored hashed). SupabaseAuthenticator is the deferred real
provider behind the same interface (ADR-0002); wiring it later touches only this
edge, not the web app.
"""

from __future__ import annotations

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


class SupabaseAuthenticator:
    """Deferred real provider (ADR-0002). Not wired in this slice."""

    def authenticate(self, email: str, password: str) -> User | None:
        raise NotImplementedError(
            "Supabase Auth is deferred; SeedAuthenticator is the offline stand-in."
        )
