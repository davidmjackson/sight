# Stage 5 Auth + Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put a login gate in front of the existing watermelon web app, behind an offline `Authenticator` seam, with one admin-only accounts view.

**Architecture:** A new `sprintsight/web/auth/` package holds password hashing, the `Authenticator` seam with an offline `SeedAuthenticator` (validates against a checked-in YAML of synthetic demo users), and session helpers over Starlette's signed-cookie `SessionMiddleware`. `create_app()` installs the middleware, gates the four existing routes (HTML redirects to `/login`, JSON returns 401), and adds `/login`, `/logout`, and an admin-only `/admin/accounts`. The real provider (Supabase Auth) is a deferred stub behind the same interface, per ADR-0002.

**Tech Stack:** Python 3.12, FastAPI / Starlette, Jinja2, PyYAML, standard-library `hashlib.pbkdf2_hmac`. New runtime deps: `itsdangerous` (session signing) and `python-multipart` (form parsing). No new crypto libraries.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-06-22-stage5-auth-accounts-design.md`. Jira: SS-34 (Epic SS-8).
- Eval-first: the test in each task is written and seen to fail before the implementation.
- Offline only: no network, no DB, no secrets required. CI stays green with no secrets.
- Passwords stored hashed (stdlib PBKDF2-HMAC-SHA256, per-user salt). Never store or log plaintext.
- Session holds only `email` and `role`. Fail closed: missing/garbled session = anonymous.
- Signing key from env `SPRINTSIGHT_SECRET_KEY`, with a clearly-labelled dev default so it runs offline.
- No em dashes in any doc text a person reads.
- Ruff lint set is `E,F,I,UP,B`, line-length 100. Run `.venv/bin/ruff check .` clean before each commit.
- Roles are exactly `admin`, `delivery_manager`, `viewer`. Only the admin gate is enforced this slice.
- Demo users (synthetic): `admin@sprintsight.test` / `admin-watermelon` (admin), `manager@sprintsight.test` / `manager-watermelon` (delivery_manager), `viewer@sprintsight.test` / `viewer-watermelon` (viewer).

---

### Task 1: Dependencies + password hashing

**Files:**
- Modify: `pyproject.toml` (web extra)
- Create: `sprintsight/web/auth/__init__.py`
- Create: `sprintsight/web/auth/hashing.py`
- Test: `tests/web/auth/__init__.py`, `tests/web/auth/test_hashing.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `new_salt() -> str` (hex)
  - `hash_password(password: str, salt_hex: str) -> str` (hex)
  - `verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool`

- [ ] **Step 1: Add the two runtime deps to the web extra**

In `pyproject.toml`, the `web` extra becomes:

```toml
web = [
  "fastapi>=0.110",
  "jinja2>=3",
  "httpx>=0.27",
  "uvicorn>=0.30",
  "itsdangerous>=2",
  "python-multipart>=0.0.9",
]
```

- [ ] **Step 2: Install the updated extra**

Run: `.venv/bin/pip install -e '.[web,dev]'`
Expected: installs `itsdangerous` and `python-multipart`, no errors.

- [ ] **Step 3: Write the failing test**

Create `tests/web/auth/__init__.py` (empty) and `tests/web/auth/test_hashing.py`:

```python
from sprintsight.web.auth.hashing import hash_password, new_salt, verify_password


def test_verify_accepts_correct_password():
    salt = new_salt()
    h = hash_password("correct horse", salt)
    assert verify_password("correct horse", salt, h) is True


def test_verify_rejects_wrong_password():
    salt = new_salt()
    h = hash_password("correct horse", salt)
    assert verify_password("battery staple", salt, h) is False


def test_new_salt_is_random_and_changes_hash():
    s1, s2 = new_salt(), new_salt()
    assert s1 != s2
    assert hash_password("pw", s1) != hash_password("pw", s2)


def test_hash_is_deterministic_for_same_salt():
    salt = new_salt()
    assert hash_password("pw", salt) == hash_password("pw", salt)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/auth/test_hashing.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.web.auth'`.

- [ ] **Step 5: Write minimal implementation**

Create `sprintsight/web/auth/__init__.py` (empty). Create `sprintsight/web/auth/hashing.py`:

```python
"""Password hashing for the offline auth stand-in (SS-34).

Standard-library PBKDF2-HMAC-SHA256. No third-party crypto. Salts are per-user;
salts and hashes are stored hex-encoded in the seed user file.
"""

import hashlib
import hmac
import os

_ALGO = "sha256"
_ITERATIONS = 100_000
_SALT_BYTES = 16


def new_salt() -> str:
    return os.urandom(_SALT_BYTES).hex()


def hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    actual = hash_password(password, salt_hex)
    return hmac.compare_digest(actual, expected_hash_hex)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/web/auth/test_hashing.py -q`
Expected: PASS (4 passed).

- [ ] **Step 7: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/web/auth tests/web/auth`
Expected: no errors.

```bash
git add pyproject.toml sprintsight/web/auth/__init__.py sprintsight/web/auth/hashing.py tests/web/auth/
git commit -m "feat(stage5): PBKDF2 password hashing + web auth deps [SS-34]"
```

---

### Task 2: Seed users + Authenticator seam

**Files:**
- Create: `sprintsight/web/auth/users.py`
- Create: `scripts/make_seed_users.py`
- Create (generated): `sprintsight/web/auth/seed_users.yaml`
- Test: `tests/web/auth/test_authenticator.py`

**Interfaces:**
- Consumes: `hash_password`, `new_salt`, `verify_password` from Task 1.
- Produces:
  - `User` frozen dataclass with `.email: str`, `.role: str`
  - `ROLES: tuple[str, ...]`
  - `Authenticator` Protocol with `authenticate(email: str, password: str) -> User | None`
  - `SeedAuthenticator()` with `.authenticate(...)` and `.all_users() -> list[User]`
  - `SupabaseAuthenticator` (deferred; `authenticate` raises `NotImplementedError`)

- [ ] **Step 1: Write the failing test**

Create `tests/web/auth/test_authenticator.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/auth/test_authenticator.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.web.auth.users'`.

- [ ] **Step 3: Write the users module**

Create `sprintsight/web/auth/users.py`:

```python
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
```

- [ ] **Step 4: Write the seed generator script**

Create `scripts/make_seed_users.py`:

```python
"""One-off generator for the synthetic demo users (SS-34).

Run from the repo root to (re)write sprintsight/web/auth/seed_users.yaml. The
demo passwords are intentionally simple: the users are synthetic and the app is
single-tenant on synthetic data. Passwords are documented in HANDOVER.
"""

from pathlib import Path

import yaml

from sprintsight.web.auth.hashing import hash_password, new_salt

DEMO_USERS = [
    ("admin@sprintsight.test", "admin", "admin-watermelon"),
    ("manager@sprintsight.test", "delivery_manager", "manager-watermelon"),
    ("viewer@sprintsight.test", "viewer", "viewer-watermelon"),
]

OUT = (
    Path(__file__).resolve().parents[1]
    / "sprintsight"
    / "web"
    / "auth"
    / "seed_users.yaml"
)


def main() -> None:
    records = []
    for email, role, password in DEMO_USERS:
        salt = new_salt()
        records.append(
            {
                "email": email,
                "role": role,
                "salt": salt,
                "hash": hash_password(password, salt),
            }
        )
    OUT.write_text(yaml.safe_dump(records, sort_keys=False))
    print(f"wrote {OUT} with {len(records)} users")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Generate the seed file**

Run: `.venv/bin/python scripts/make_seed_users.py`
Expected: prints `wrote .../seed_users.yaml with 3 users`; the file exists and contains three entries, each with `email`, `role`, `salt`, `hash` and NO plaintext password.

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/web/auth/test_authenticator.py -q`
Expected: PASS (6 passed).

- [ ] **Step 7: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/web/auth scripts tests/web/auth`
Expected: no errors.

```bash
git add sprintsight/web/auth/users.py scripts/make_seed_users.py sprintsight/web/auth/seed_users.yaml tests/web/auth/test_authenticator.py
git commit -m "feat(stage5): Authenticator seam + synthetic seed users [SS-34]"
```

---

### Task 3: Session helpers + middleware secret

**Files:**
- Create: `sprintsight/web/auth/session.py`
- Test: `tests/web/auth/test_session.py`

**Interfaces:**
- Consumes: `User` from Task 2.
- Produces:
  - `SESSION_KEY: str`
  - `session_secret() -> str`
  - `login_session(request, user: User) -> None`
  - `logout_session(request) -> None`
  - `session_user(request) -> User | None`
  - `require_api_user(request) -> User` (raises `HTTPException(401)` when anonymous)

Note: `request` is anything exposing a mutable `.session` mapping. The unit test uses a tiny fake; the real Starlette `Request` provides `.session` once `SessionMiddleware` is installed (Task 4).

- [ ] **Step 1: Write the failing test**

Create `tests/web/auth/test_session.py`:

```python
import os

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
    assert session_secret() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/auth/test_session.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.web.auth.session'`.

- [ ] **Step 3: Write the session module**

Create `sprintsight/web/auth/session.py`:

```python
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
```

Note: type-hinting the fake as `Request` is fine at runtime; `from __future__ import annotations` keeps the annotations from being evaluated, and the functions only touch `.session`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/web/auth/test_session.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/web/auth tests/web/auth`
Expected: no errors.

```bash
git add sprintsight/web/auth/session.py tests/web/auth/test_session.py
git commit -m "feat(stage5): session helpers + auth dependency [SS-34]"
```

---

### Task 4: Login / logout routes + templates + middleware

**Files:**
- Modify: `sprintsight/web/app.py`
- Create: `sprintsight/web/templates/login.html`
- Modify: `sprintsight/web/templates/base.html`
- Modify: `sprintsight/web/static/app.css` (small additions)
- Test: `tests/web/test_auth_flow.py`

**Interfaces:**
- Consumes: `SeedAuthenticator` (Task 2); `login_session`, `logout_session`, `session_secret` (Task 3).
- Produces: routes `GET /login`, `POST /login`, `GET /logout`; `SessionMiddleware` installed on the app; `base.html` header shows the logged-in user + logout, or a login link.

This task adds the routes and middleware but does NOT yet gate `/`, `/team`, or the API (that is Task 5). After login, `POST /login` redirects to `/`, which still serves anonymously until Task 5.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_auth_flow.py`:

```python
from fastapi.testclient import TestClient

from sprintsight.web.app import create_app


def _client():
    return TestClient(create_app())


def test_login_page_renders_form():
    resp = _client().get("/login")
    assert resp.status_code == 200
    assert 'name="email"' in resp.text
    assert 'name="password"' in resp.text


def test_login_valid_redirects_and_sets_session_cookie():
    client = _client()
    resp = client.post(
        "/login",
        data={"email": "admin@sprintsight.test", "password": "admin-watermelon"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert "session" in resp.cookies


def test_login_wrong_password_shows_error_no_session():
    client = _client()
    resp = client.post(
        "/login",
        data={"email": "admin@sprintsight.test", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "invalid" in resp.text.lower()
    assert "session" not in resp.cookies


def test_logout_clears_session():
    client = _client()
    client.post(
        "/login",
        data={"email": "admin@sprintsight.test", "password": "admin-watermelon"},
        follow_redirects=False,
    )
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_auth_flow.py -q`
Expected: FAIL (`GET /login` returns 404, no such route yet).

- [ ] **Step 3: Add middleware, authenticator, and auth routes to app.py**

Replace the contents of `sprintsight/web/app.py` with:

```python
"""Stage 6 FastAPI app (SS-6) + Stage 5 auth gate (SS-34)."""

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from sprintsight.web import service
from sprintsight.web.auth.session import login_session, logout_session, session_secret
from sprintsight.web.auth.users import SeedAuthenticator

_HERE = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="Sprintsight watermelon detector")
    app.add_middleware(
        SessionMiddleware, secret_key=session_secret(), same_site="lax", https_only=False
    )
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")
    authenticator = SeedAuthenticator()

    @app.get("/login", response_class=HTMLResponse)
    def page_login(request: Request) -> HTMLResponse:
        return _TEMPLATES.TemplateResponse(
            request, "login.html", {"error": None, "user": None}
        )

    @app.post("/login")
    def do_login(
        request: Request, email: str = Form(...), password: str = Form(...)
    ):
        user = authenticator.authenticate(email, password)
        if user is None:
            return _TEMPLATES.TemplateResponse(
                request,
                "login.html",
                {"error": "Invalid email or password.", "user": None},
                status_code=200,
            )
        login_session(request, user)
        return RedirectResponse("/", status_code=303)

    @app.get("/logout")
    def do_logout(request: Request) -> RedirectResponse:
        logout_session(request)
        return RedirectResponse("/login", status_code=303)

    @app.get("/api/portfolio")
    def api_portfolio() -> list[dict]:
        return [asdict(row) for row in service.portfolio()]

    @app.get("/api/team/{team_id}")
    def api_team(team_id: str) -> dict:
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return asdict(detail)

    @app.get("/", response_class=HTMLResponse)
    def page_portfolio(request: Request) -> HTMLResponse:
        return _TEMPLATES.TemplateResponse(
            request, "portfolio.html", {"rows": service.portfolio(), "user": None}
        )

    @app.get("/team/{team_id}", response_class=HTMLResponse)
    def page_team(request: Request, team_id: str) -> HTMLResponse:
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return _TEMPLATES.TemplateResponse(request, "team.html", {"d": detail, "user": None})

    return app


app = create_app()
```

Note: this import block includes only what Task 4 uses, so it lints clean on its own. Task 5 extends the import block when it wires the gating dependencies.

- [ ] **Step 4: Create the login template**

Create `sprintsight/web/templates/login.html`:

```html
{% extends "base.html" %}
{% block title %}Sign in - Sprintsight{% endblock %}
{% block main %}
<section class="login">
  <h1>Sign in</h1>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post" action="/login" class="login-form">
    <label>Email
      <input type="email" name="email" autocomplete="username" required>
    </label>
    <label>Password
      <input type="password" name="password" autocomplete="current-password" required>
    </label>
    <button type="submit">Sign in</button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 5: Update the base header**

Replace the `<header>` line in `sprintsight/web/templates/base.html` with:

```html
  <header>
    <a href="/" class="brand">Sprintsight</a> <span class="sub">watermelon detector</span>
    <span class="session">
      {% if user %}{{ user.email }} ({{ user.role }}) &middot; <a href="/logout">Sign out</a>
      {% else %}<a href="/login">Sign in</a>{% endif %}
    </span>
  </header>
```

- [ ] **Step 6: Add minimal styling**

Append to `sprintsight/web/static/app.css`:

```css
.session { float: right; font-size: 0.85rem; }
.login { max-width: 22rem; margin: 2rem auto; }
.login-form label { display: block; margin: 0.75rem 0; }
.login-form input { width: 100%; padding: 0.4rem; }
.error { color: #b00020; }
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/bin/pytest tests/web/test_auth_flow.py -q`
Expected: PASS (4 passed).

- [ ] **Step 8: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/web tests/web`
Expected: no errors. (If F401 on `Depends`/`require_api_user`/`User`, proceed to Task 5 edits before committing.)

```bash
git add sprintsight/web/app.py sprintsight/web/templates/login.html sprintsight/web/templates/base.html sprintsight/web/static/app.css tests/web/test_auth_flow.py
git commit -m "feat(stage5): login/logout routes + session middleware [SS-34]"
```

---

### Task 5: Gate the existing routes + update existing tests

**Files:**
- Modify: `sprintsight/web/app.py` (the four existing routes)
- Create: `tests/web/conftest.py`
- Modify: `tests/web/test_pages.py`
- Modify: `tests/web/test_api.py`
- Test (new cases): `tests/web/test_auth_flow.py` (append)

**Interfaces:**
- Consumes: `session_user`, `require_api_user` (Task 3); the login flow (Task 4).
- Produces: a shared `tests/web/conftest.py` with fixtures `anon_client`, `client` (admin), `viewer_client`, `manager_client`, and constants `ADMIN`, `MANAGER`, `VIEWER`.

- [ ] **Step 1: Write the failing gating tests**

Append to `tests/web/test_auth_flow.py`:

```python
def test_anonymous_html_redirects_to_login():
    resp = _client().get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_anonymous_team_page_redirects_to_login():
    resp = _client().get("/team/atlas", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_anonymous_api_portfolio_returns_401():
    assert _client().get("/api/portfolio").status_code == 401


def test_anonymous_api_team_returns_401():
    assert _client().get("/api/team/atlas").status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/web/test_auth_flow.py -q`
Expected: FAIL (anonymous `/` returns 200, `/api/portfolio` returns 200; routes not gated yet).

- [ ] **Step 3: Extend the imports, then gate the four routes**

First, update the two auth import lines in `sprintsight/web/app.py` to pull in the gating helpers:

```python
from fastapi import Depends, FastAPI, Form, HTTPException, Request
...
from sprintsight.web.auth.session import (
    login_session,
    logout_session,
    require_api_user,
    session_secret,
    session_user,
)
from sprintsight.web.auth.users import SeedAuthenticator, User
```

Then replace the four route definitions (`api_portfolio`, `api_team`, `page_portfolio`, `page_team`) with:

```python
    @app.get("/api/portfolio")
    def api_portfolio(user: User = Depends(require_api_user)) -> list[dict]:
        return [asdict(row) for row in service.portfolio()]

    @app.get("/api/team/{team_id}")
    def api_team(team_id: str, user: User = Depends(require_api_user)) -> dict:
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return asdict(detail)

    @app.get("/", response_class=HTMLResponse)
    def page_portfolio(request: Request) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request, "portfolio.html", {"rows": service.portfolio(), "user": user}
        )

    @app.get("/team/{team_id}", response_class=HTMLResponse)
    def page_team(request: Request, team_id: str) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return _TEMPLATES.TemplateResponse(request, "team.html", {"d": detail, "user": user})
```

- [ ] **Step 4: Add the shared test fixtures**

Create `tests/web/conftest.py`:

```python
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
```

- [ ] **Step 5: Update test_pages.py to use the authenticated fixture**

Replace the contents of `tests/web/test_pages.py` with:

```python
def test_portfolio_page_lists_all_teams(client):
    resp = client.get("/")
    assert resp.status_code == 200
    for team in ("Atlas", "Boreas", "Cygnus", "Draco", "Echo"):
        assert team in resp.text


def test_portfolio_page_flags_atlas(client):
    resp = client.get("/")
    assert "watermelon" in resp.text.lower()


def test_team_page_atlas_shows_evidence_and_signals(client):
    resp = client.get("/team/atlas")
    assert resp.status_code == 200
    assert "red" in resp.text.lower()
    assert "status-atlas-s15" in resp.text
    assert "burn ratio" in resp.text.lower()


def test_team_page_unknown_404(client):
    assert client.get("/team/nope").status_code == 404
```

- [ ] **Step 6: Update test_api.py to use the authenticated fixture**

Replace the contents of `tests/web/test_api.py` with:

```python
def test_api_portfolio_verdicts(client):
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    rows = {row["team"]: row for row in resp.json()}
    assert rows["Atlas"]["is_watermelon"] is True
    assert rows["Atlas"]["actual_status"] == "red"
    assert rows["Boreas"]["is_watermelon"] is False
    assert rows["Echo"]["has_verdict"] is False


def test_api_team_atlas_detail(client):
    resp = client.get("/api/team/atlas")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_watermelon"] is True
    ids = {e["artifact_id"] for e in body["evidence"]}
    assert "slack-atlas-s15-msg-dep" in ids
    assert body["signals"]


def test_api_team_unknown_404(client):
    assert client.get("/api/team/nope").status_code == 404
```

- [ ] **Step 7: Run the whole web suite**

Run: `.venv/bin/pytest tests/web -q`
Expected: PASS (all web tests green, including the new gating cases).

- [ ] **Step 8: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/web tests/web`
Expected: no errors.

```bash
git add sprintsight/web/app.py tests/web/conftest.py tests/web/test_pages.py tests/web/test_api.py tests/web/test_auth_flow.py
git commit -m "feat(stage5): gate portfolio + API behind login [SS-34]"
```

---

### Task 6: Admin-only accounts view

**Files:**
- Modify: `sprintsight/web/app.py` (add `/admin/accounts`)
- Create: `sprintsight/web/templates/admin_accounts.html`
- Test: `tests/web/test_admin.py`

**Interfaces:**
- Consumes: `session_user` (Task 3); `SeedAuthenticator.all_users()` (Task 2); fixtures from Task 5.
- Produces: route `GET /admin/accounts`.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_admin.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/web/test_admin.py -q`
Expected: FAIL (`/admin/accounts` is 404).

- [ ] **Step 3: Add the admin route**

In `sprintsight/web/app.py`, add this route inside `create_app()` (after `page_team`, before `return app`):

```python
    @app.get("/admin/accounts", response_class=HTMLResponse)
    def page_admin_accounts(request: Request) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="admin only")
        return _TEMPLATES.TemplateResponse(
            request,
            "admin_accounts.html",
            {"user": user, "accounts": authenticator.all_users()},
        )
```

- [ ] **Step 4: Create the admin template**

Create `sprintsight/web/templates/admin_accounts.html`:

```html
{% extends "base.html" %}
{% block title %}Accounts - Sprintsight{% endblock %}
{% block main %}
<section class="accounts">
  <h1>Accounts</h1>
  <p class="sub">Admin only. Synthetic demo users.</p>
  <table>
    <thead><tr><th>Email</th><th>Role</th></tr></thead>
    <tbody>
      {% for a in accounts %}
      <tr><td>{{ a.email }}</td><td>{{ a.role }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/web/test_admin.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Lint and commit**

Run: `.venv/bin/ruff check sprintsight/web tests/web`
Expected: no errors.

```bash
git add sprintsight/web/app.py sprintsight/web/templates/admin_accounts.html tests/web/test_admin.py
git commit -m "feat(stage5): admin-only accounts view [SS-34]"
```

---

### Task 7: Full verification + docs

**Files:**
- Modify: `HANDOVER.md`

**Interfaces:** none (verification + documentation only).

- [ ] **Step 1: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all tests pass (the previous 118 + the new auth tests), no failures. Skips unchanged.

- [ ] **Step 2: Run the full lint**

Run: `.venv/bin/ruff check .`
Expected: no errors.

- [ ] **Step 3: Confirm the deterministic eval gates still pass**

Run: `.venv/bin/python scripts/run_watermelon_eval.py && .venv/bin/python scripts/run_report_eval.py`
Expected: watermelon 4/4 and report 4/4 (unchanged).

- [ ] **Step 4: Smoke-run the server (optional, manual)**

Run: `.venv/bin/uvicorn sprintsight.web.app:app --port 8011 &` then `sleep 2 && curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8011/` and expect `303` (redirect to login). Stop the server afterward.

- [ ] **Step 5: Update HANDOVER**

In `HANDOVER.md`: update the "Where we are" line to record Stage 5 first slice (SS-34) complete on branch `stage5-auth-accounts`: auth gate + Authenticator seam (offline `SeedAuthenticator`, deferred `SupabaseAuthenticator`), three synthetic demo users (passwords documented: admin/admin-watermelon, manager/manager-watermelon, viewer/viewer-watermelon), login/logout, four routes gated (HTML redirect, API 401), admin-only `/admin/accounts`. Note new env var `SPRINTSIGHT_SECRET_KEY` (dev default offline). Add ONE line to the `Learning queue` section: `auth seam + session cookie | why we fake the identity provider offline like the DB/embedder, and what a signed session cookie is | sprintsight/web/auth/ | 2026-06-22`.

- [ ] **Step 6: Commit**

```bash
git add HANDOVER.md
git commit -m "docs(stage5): HANDOVER + learning-queue flag for the auth slice [SS-34]"
```

---

## Notes for the executor

- Do not edit `LEARNING-LOG.md`. Only append the one flag line to the HANDOVER `Learning queue` (Task 7, Step 5).
- The Jira move (SS-34 In Review, then Done after review) is driven from the main session via Composio, not from this plan.
- Real Supabase wiring, signup/reset/email, the viewer-vs-manager split, and multi-tenant `tenant_id` are explicitly out of scope.
