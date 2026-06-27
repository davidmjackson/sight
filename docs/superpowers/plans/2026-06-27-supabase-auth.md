# Plan — real Supabase Auth wiring

Spec: docs/superpowers/specs/2026-06-27-supabase-auth-design.md
Branch: realwiring-supabase-auth

Swap the auth backend behind the existing `Authenticator` seam; offline-by-default; fully
offline-testable (the one network call is faked). No session-model change.

1. **Tests first (red)** — `tests/web/auth/test_supabase_auth.py`: pure mappers (`_role_from`
   app_metadata-only incl. the security case that a self-set `user_metadata.role` is ignored;
   `_user_from_auth`), `authenticate()` with `_password_grant` faked (success->User, failure->None),
   `all_users()==[]`, and the `make_authenticator()`/`_supabase_configured()` gate.

2. **Implement (green)** — in `sprintsight/web/auth/users.py`: real `SupabaseAuthenticator`
   (frozen dataclass: base_url + anon_key; walled `_password_grant` via lazy httpx; pure
   `_user_from_auth`/`_role_from`; `all_users()->[]`), add `all_users()` to the `Authenticator`
   Protocol, and `make_authenticator()` gated on `SPRINTSIGHT_AUTH=supabase` + SUPABASE_URL +
   SUPABASE_ANON_KEY. `app.py` calls `make_authenticator()` instead of hard-coding SeedAuthenticator.

3. **Tidy** — drop the obsolete "stub is deferred" test; keep the suite green (default backend
   unchanged).

4. **Runbook** — `docs/auth/supabase-auth.md` (create users, set app_metadata.role, set the flag,
   verify).

5. **Verify** — full suite + ruff + deterministic eval gates green; independent review; merge. CI is
   offline (no flag), so the suite is the proof; live login is an operator step.

Result: 308 passed (+12 supabase, -1 obsolete) + 4 skipped, ruff clean, eval gates unchanged.

## Decisions
- Role from app_metadata ONLY (user_metadata is self-editable -> escalation risk).
- Direct GoTrue HTTPS with the anon key (no supabase-py dep; least privilege; service-role unused).
- Keep our signed-cookie session; do not store/refresh Supabase JWTs.

## Deferred
- JWT storage/refresh, OAuth/SSO, signup/reset/email flows; admin user-listing via the admin API;
  live verification (operator).
