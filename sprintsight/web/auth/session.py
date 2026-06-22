"""Session + auth dependencies for the web app (SS-34).

Signed-cookie session (Starlette SessionMiddleware). The session stores only the
user's email and role. Fails closed: a missing or unreadable session is anonymous.
"""

from __future__ import annotations

import os

from fastapi import HTTPException, Request

from sprintsight.web.auth.users import User

SESSION_KEY = "user"
_DEV_SECRET = "dev-only-insecure-secret-change-me"


def session_secret() -> str:
    return os.environ.get("SPRINTSIGHT_SECRET_KEY", _DEV_SECRET)


def login_session(request: Request, user: User) -> None:
    request.session[SESSION_KEY] = {"email": user.email, "role": user.role}


def logout_session(request: Request) -> None:
    request.session.pop(SESSION_KEY, None)


def session_user(request: Request) -> User | None:
    data = request.session.get(SESSION_KEY)
    if not isinstance(data, dict) or "email" not in data or "role" not in data:
        return None
    return User(email=data["email"], role=data["role"])


def require_api_user(request: Request) -> User:
    user = session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user
