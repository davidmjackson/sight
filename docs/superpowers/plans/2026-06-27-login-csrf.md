# Plan — slice 5: login CSRF protection

Spec: docs/superpowers/specs/2026-06-27-login-csrf-design.md
Branch: realwiring-login-csrf

Eval-first, synchronizer-token CSRF on `POST /login`. No new deps (stdlib `secrets`).

1. **Tests first (red)** — `tests/web/auth/test_csrf.py` (6): form renders a token; POST with no
   token rejected (400, no session); wrong token rejected; valid token succeeds (303); token tied
   to its own session (another session's token rejected); CSRF checked before password.

2. **Guard (green)** — `sprintsight/web/auth/session.py`: `issue_csrf(request)` (mint-and-store one
   token per session in the signed cookie) + `valid_csrf(request, token)` (constant-time compare,
   fails closed).

3. **Wire** — `app.py`: `GET /login` issues the token into the template; `POST /login` takes
   `csrf_token: str = Form("")` and rejects (re-render login, 400, fresh token) BEFORE
   authentication if invalid. `login.html`: hidden `csrf_token` field.

4. **Keep the suite green through the guard** — `tests/web/conftest.py`: a `csrf_token(client)`
   helper + the shared `login()` helper now GETs the form for a token before posting;
   `test_auth_flow.py`: the three direct login POSTs fetch a token first.

5. **Verify** — full suite, ruff, deterministic eval gates (watermelon 4/4, report 4/4, cross-tool
   7/7); then an independent whole-branch review.

Result: 289 passed (+6) + 4 skipped, ruff clean, eval gates unchanged.

## Deferred (own later slices)
- Real Supabase Auth wiring (`SupabaseAuthenticator`) — needs a live Supabase project (operator).
- Per-tenant RLS policies — needs a least-privilege non-owner DB role + a per-request tenant GUC
  (the `postgres` owner bypasses RLS today).
- CSRF on `GET /logout`; Origin/Referer allow-listing.
