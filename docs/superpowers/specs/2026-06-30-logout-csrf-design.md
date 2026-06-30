# Logout CSRF protection — design note

Plain-English summary: signing out used to be a plain link (`GET /logout`). A link or
redirect is something another website can trigger on your behalf, so a malicious page
could quietly sign you out. This slice turns sign-out into a form submission (`POST`)
that carries a secret per-session token the server checks first, so only a real click of
our own "Sign out" button can end your session. It is the same protection we already put
on the login form. Nothing about who you are or what you can see changes.

## The gap

`GET /logout` cleared the session with no token check, triggered by an `<a href="/logout">`
link in the shared shell. That is a textbook **logout-CSRF**: a cross-site request can end
a victim's session (an annoyance / availability nuisance, not a data breach).

Honest nuance on `SameSite=Lax` (the session cookie's setting): Lax already withholds the
cookie from cross-site **sub-resource** requests like `<img src=".../logout">`, so that
particular vector was already dead. But Lax still sends the cookie on a cross-site
**top-level GET navigation** (a link click or `window.location = ".../logout"`), because GET
is treated as a "safe" navigation. Converting to POST closes that residual path (Lax does
not attach the cookie to a cross-site top-level POST) and the synchronizer token is belt-and-
braces on top. So this is a real, if low-severity, hardening, not a no-op.

## The change (presentation + one route, no auth-model change)

- `GET /logout` -> **`POST /logout`** with `csrf_token: str = Form("")`. The CSRF check runs
  first; an invalid/missing token raises a clean `400` and the session is left intact
  (**fail closed** — a forged logout does nothing). A valid token clears the session and
  303-redirects to `/login`, exactly as before.
- The shared shell `base.html` renders a small `POST /logout` form with a hidden
  `csrf_token` instead of the link. `issue_csrf` is registered as a Jinja global so the
  four authenticated routes (portfolio, team, crosstool, admin) need not each thread the
  token through their context. The token is per-session and reused (the same one login
  mints), so it is already present by the time any authenticated page renders.
- A `.logout-form{display:inline-flex; margin:0}` rule keeps the button inline in the topbar.

Reuses the existing `issue_csrf`/`valid_csrf` synchronizer-token helpers from the login-CSRF
slice unchanged. No new dependency. Detector / report / auth / eval logic untouched.

## Eval-first

`tests/web/auth/test_logout_csrf.py` (6 cases) proves the security property, not just status
codes: a missing token, a wrong token, a non-ASCII forged token, and a `GET` all leave the
user **still signed in**; only a valid-token POST signs out; the authenticated shell renders
the POST form with a token. The existing `test_auth_flow.py` logout test was updated to the
POST contract. Full suite green (369 passed, 4 skipped), ruff clean, eval gates unchanged.
