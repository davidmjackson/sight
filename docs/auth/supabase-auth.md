# Switching login to real Supabase Auth (operator runbook)

Plain-English: by default the app checks passwords against a checked-in file of demo users. This
turns on real Supabase Auth instead, behind a fail-safe flag. CI/tests/local keep using the file
backend unless you set the flag.

## What CI already proves
The offline suite (`tests/web/auth/test_supabase_auth.py`) proves the response->User mapping,
fail-closed behaviour, the role-from-`app_metadata`-only rule, and the gate. Only the live login
below is manual (it needs a real Supabase project + a real user).

## One-time setup (operator)

1. In Supabase, create the user(s) under Authentication (or invite them). Confirm their email if
   email confirmation is on, or they cannot sign in.

2. Give each user a role the app understands (`admin` | `delivery_manager` | `viewer`) in their
   **app_metadata** (NOT user_metadata — the app deliberately ignores user_metadata so a user
   cannot self-promote). In the Supabase SQL editor:

   `update auth.users set raw_app_meta_data = raw_app_meta_data || '{"role":"admin"}' where email = 'you@example.com';`

   A user with no role defaults to the least-privileged `viewer`.

3. Turn the backend on in the app's environment (`.env` already has `SUPABASE_URL` and
   `SUPABASE_ANON_KEY` from earlier slices):

   `SPRINTSIGHT_AUTH=supabase`

   The app uses the **anon** key for the password grant (least privilege); the service-role key is
   not used for login.

## Verify
- Log in at `/login` with a real Supabase user's email + password -> redirected to the portfolio.
- A wrong password (or an unconfirmed user) stays on `/login` with an error (fails closed).
- The user's role drives the admin page gate (only `admin` may open `/admin/accounts`).

## Notes
- The app does NOT store the Supabase JWT; it issues its own signed session cookie after a
  successful check (session model unchanged), so CSRF + the existing session rules still apply.
- If Supabase is unreachable, logins fail (never fail open). Unset `SPRINTSIGHT_AUTH` to fall back
  to the offline seed users.
- The admin accounts page lists no users under the Supabase backend (accounts are managed in the
  Supabase dashboard); listing via the admin API is a later enhancement.
- Keep the anon key in `.env`/the deploy secret store, never in git.
