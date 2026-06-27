# Slice — real Supabase Auth wiring (real-wiring, Epic SS-5)

Plain-English summary (read this first)
---------------------------------------
Today login checks a password against a checked-in file of demo users (`SeedAuthenticator`). This
slice lets the app instead verify the password against **Supabase Auth** (the real, managed
identity service), behind the same fail-safe gate as our other integrations: offline file-based
login by default, real Supabase login only when `SPRINTSIGHT_AUTH=supabase` plus the Supabase keys
are set. Nothing else about login changes: the app still issues its own signed session cookie after
a successful check (we are swapping only the "is this password valid + what role" step).

Design forks, decided
---------------------
- **Transport: direct HTTPS to GoTrue, not supabase-py.** One POST to
  `{SUPABASE_URL}/auth/v1/token?grant_type=password` with the **anon** key as `apikey` (the correct
  least-privilege client flow; the service-role key is NOT used). Uses `httpx` (already a web dep),
  imported lazily. No new dependency. Matches the connector slice's "wall the one network call,
  keep the mapper pure" shape.
- **Session model unchanged (keep our signed cookie).** `SupabaseAuthenticator.authenticate` only
  *verifies* credentials and returns `User(email, role)`; the app keeps issuing its own session
  exactly as today. We do NOT store/refresh Supabase JWTs — that would be a much larger change and
  is unnecessary to swap the auth backend behind the existing `Authenticator` seam.
- **Role comes ONLY from `app_metadata.role` (security-critical).** Supabase users can self-edit
  their `user_metadata`, so reading a role from there would let a user make themselves admin. We
  read the role only from `app_metadata` (admin-controlled), validate it against `ROLES`, and
  default to the least-privileged `viewer` otherwise.
- **Fail closed.** Bad credentials, an unconfirmed user, a non-200, a network error, or an
  unparseable body all yield `None` -> login fails. If Supabase is unreachable, nobody logs in
  (correct for a real auth backend; we never fail open).

In scope
--------
1. Implement `SupabaseAuthenticator` (replacing the stub) in `sprintsight/web/auth/users.py`:
   - `_password_grant(email, password) -> dict | None`: the ONLY network call (lazy `httpx`),
     walled off; returns the parsed JSON on 200, else None.
   - `_user_from_auth(data) -> User | None` + `_role_from(user) -> str`: pure mappers (hard-tested).
   - `authenticate()` orchestrates; `all_users() -> []` (Supabase accounts are managed in the
     Supabase dashboard; admin-listing via the admin API is deferred).
2. Add `all_users()` to the `Authenticator` Protocol so the seam is explicit (the admin page uses
   it). `SeedAuthenticator` already satisfies it.
3. A fail-safe factory `make_authenticator()` + `_supabase_configured()` gate; `create_app()` calls
   it instead of hard-coding `SeedAuthenticator()`. Default (no flag) = `SeedAuthenticator`, so CI,
   tests, and local runs are byte-for-byte unchanged.
4. `docs/auth/supabase-auth.md`: operator runbook (create users in Supabase, set `app_metadata.role`,
   set the flag + keys, verify a login).

Out of scope (named, not forgotten)
-----------------------------------
- Storing/validating/refreshing Supabase JWTs; SSO/OAuth providers; signup / password-reset /
  email flows (managed in Supabase).
- Admin user-listing against the Supabase admin API (needs the service-role key) — `all_users()`
  returns [] under the Supabase backend for now.
- Live verification against a real Supabase project (operator step; CI proves the logic offline).

Eval-first
----------
Auth is enforcement logic, so the eval is a deterministic offline test suite (no network): the pure
mappers (email+role; `app_metadata` wins; **a `user_metadata.role=admin` is ignored -> viewer**;
missing email -> None), `authenticate()` with `_password_grant` faked (success -> User, failure ->
None), and the gate/factory (SeedAuthenticator by default; SupabaseAuthenticator only with flag +
URL + anon key). The existing auth + web suites stay green (default backend unchanged). Deterministic
watermelon/report/cross-tool gates untouched.

Security
--------
Least privilege (anon key only, never service-role). Role cannot be self-escalated (app_metadata
only). Fails closed. No new persisted data; the app session model is unchanged. The anon key/URL
live in `.env`/the deploy secret store, never in git.
