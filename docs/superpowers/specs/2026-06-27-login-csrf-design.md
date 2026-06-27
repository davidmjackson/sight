# Slice 5 — login CSRF protection (real-wiring / auth hardening, Epic SS-5)

Plain-English summary (read this first)
---------------------------------------
"CSRF" = Cross-Site Request Forgery: a malicious page in another tab quietly submits our login
form for you, logging you into an account the attacker controls (so your later actions land in
their account). The fix is a secret one-time token: the sign-in page plants a hidden token tied to
your browser session, and the server refuses any login POST that does not carry the matching token.
An attacker's page cannot read your token, so its forged POST is rejected.

This was the one security item deferred when we first built auth (session 10, SS-34). It is fully
offline and testable with no live credentials, so it is the natural next real-wiring slice. The
companion auth-hardening items (real Supabase Auth wiring, per-tenant RLS policies) stay as their
own later slices.

In scope
--------
1. A synchronizer-token CSRF guard for the only state-changing form we have, `POST /login`:
   - `GET /login` issues a random token, stores it in the signed session cookie, and renders it as
     a hidden field.
   - `POST /login` rejects the request (re-renders the login page with an error, HTTP 400) unless
     the submitted `csrf_token` matches the session's token (constant-time compare). The CSRF check
     runs BEFORE the password check, so a forged POST never reaches authentication.
2. Tests written first (eval-first): the form carries a token; a POST with no token is rejected; a
   POST with a wrong token is rejected; a POST with the right token succeeds; a token from one
   session is not valid in another; valid creds + valid token still sets the session.
3. Update the shared test login helper (and the direct login POSTs in `test_auth_flow.py`) to fetch
   the token first, so the existing suite keeps passing through the new guard.

Out of scope (named, not forgotten)
-----------------------------------
- Real Supabase Auth wiring (`SupabaseAuthenticator` stays the deferred stub) — needs a live
  Supabase project; operator step, like every prior live-wire slice.
- Per-tenant RLS policies — needs a least-privilege non-owner DB role + a per-request tenant GUC
  (the `postgres` owner bypasses RLS today), so it is its own slice.
- CSRF on `GET /logout` — logout is a GET with low impact and `same_site=lax` already blocks the
  cross-site cookie; converting logout to a CSRF-protected POST is a small later tidy.
- Origin/Referer allow-listing — the synchronizer token is the primary, sufficient defense; an
  Origin check needs a configured allowed host and can be layered later.

Design
------
### `sprintsight/web/auth/session.py`
```
CSRF_KEY = "csrf"

def issue_csrf(request) -> str:
    token = request.session.get(CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_KEY] = token
    return token

def valid_csrf(request, token) -> bool:
    expected = request.session.get(CSRF_KEY)
    return bool(expected) and bool(token) and secrets.compare_digest(token, expected)
```
One token per session, reused across renders (tab-friendly). The token lives in the existing
signed session cookie (Starlette `SessionMiddleware`), so it is set even pre-login and cannot be
read or forged by another origin.

### `sprintsight/web/app.py`
- `GET /login`: `token = issue_csrf(request)`; pass `csrf_token=token` to the template.
- `POST /login`: add `csrf_token: str = Form("")`. First: `if not valid_csrf(request, csrf_token):`
  re-render login with `error="Your session expired. Please try again."`, `status_code=400`, and a
  fresh token (so the retry works). Only then run `authenticator.authenticate(...)`.
- The invalid-password re-render also passes a token (reused from the session).

### `sprintsight/web/templates/login.html`
Add inside the form: `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.

Security
--------
No new deps (stdlib `secrets`). No new persisted data; the token rides the existing session cookie.
Fails closed: no session token (e.g. a direct POST that never fetched the form) → rejected. The
guard is ordered before authentication so a forged request cannot probe credentials. `same_site=lax`
remains as defense in depth.

Eval-first
----------
`tests/web/auth/test_csrf.py` is the eval (auth is enforcement logic, so the eval is a deterministic
test suite). The shared `login()` helper in `tests/web/conftest.py` is updated to GET the form and
extract the token before posting, so the whole existing suite exercises the guard. Deterministic
watermelon (4/4) + report (4/4) + cross-tool (7/7) eval gates are untouched and stay the CI gate.
