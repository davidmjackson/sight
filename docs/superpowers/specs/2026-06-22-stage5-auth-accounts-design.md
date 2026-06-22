# Stage 5 first slice — Auth + Accounts (SS-8)

- **Epic:** SS-8 (Stage 5, Accounts / Auth / Admin)
- **Date:** 2026-06-22
- **Status:** Approved design (David), pre-implementation
- **Branch:** `stage5-auth-accounts`

## Plain-English summary (read this first)

We put a login screen in front of the watermelon app. To see anything (the
portfolio grid, a team drill-in, or the raw JSON), you must log in first. Each
user has a role. One admin-only page lists who has access. Like everything else
in this project, it runs fully offline against a small set of demo users, with
no database and no secrets needed. The "real" provider (Supabase Auth) slots in
later behind the same seam, touching the edge of the system rather than the app.

## Context and prior decisions (not re-opened)

- **ADR-0002** locked the auth provider: managed **Supabase Auth**, UK/EU region.
  Roles are handled in our **own app layer** via a three-value enum
  (`admin` / `delivery_manager` / `viewer`, schema decision D4), kept portable so
  the provider is swappable.
- The whole system is built **offline-first** with injected seams and local
  stand-ins (embedder, store, report-writer). CI is green with no secrets and the
  app is demoable offline. See `[[offline-standins-and-open-wiring]]`.
- The Stage 6 web layer (`sprintsight/web/`) currently exposes four **open**
  routes: `/`, `/team/{id}`, `/api/portfolio`, `/api/team/{id}`. It is read-only;
  there are no writes and no settings, so there is nothing today that a
  `delivery_manager` can do that a `viewer` cannot.

## Decisions taken in brainstorming

1. **Realness:** seam + offline stand-in now; real Supabase Auth deferred behind
   the seam. (Keeps CI green / no secrets / offline demo, consistent with the
   rest of the build.)
2. **Role scope:** authenticate everything; model all three roles on the session;
   enforce exactly **one** role gate (an admin-only accounts view). No
   viewer-vs-manager distinction yet, because no feature needs it.

## Scope

### In scope
- An `Authenticator` seam and an offline `SeedAuthenticator` stand-in.
- A seed file of three demo users (one per role), passwords stored **hashed**.
- A `/login` page (email + password) and `/logout`.
- A signed session cookie carrying the user's email and role.
- Auth gate on the four existing routes: HTML routes redirect to `/login` when
  anonymous; API routes return `401`.
- One admin-only route `/admin/accounts` listing the seed users; non-admins `403`.
- Tests first (eval-first), defining "done". Existing Stage 6 tests updated to
  log in first.

### Out of scope (deliberately deferred)
- Real Supabase Auth wiring (named TODO behind the seam).
- Signup, password reset, email verification, any account self-service.
- The viewer-vs-delivery_manager distinction (no feature needs it yet).
- Multi-tenant / `tenant_id` enforcement (schema decision D2, still deferred).
- Any write action or RAID action.

## Architecture

### 1. The seam — `Authenticator`
A single-purpose interface: given an email and password, return an authenticated
user (email + role) or `None`.

- `SeedAuthenticator` (offline stand-in): validates credentials against the seed
  user file. Runs in CI, no secrets, no network.
- `SupabaseAuthenticator` (deferred): a named TODO implementing the same
  interface. Wiring it later changes the edge, not the app. Mirrors the
  embedder / store / report-writer seam pattern.

Lives under `sprintsight/web/auth/` (new package) so the web layer stays cohesive
and `service.py` (the data layer) is untouched.

### 2. Accounts — seed users
A seed file (`data/users.yaml`, exact path confirmed at implementation) with three
users: one `admin`, one `delivery_manager`, one `viewer`. Each entry:
`email`, `role`, and a **password hash** (Python standard-library
`hashlib.pbkdf2_hmac` with a per-user salt; **zero new runtime dependencies**).
Plain-text passwords are never stored or logged. The demo passwords are recorded
in the spec/HANDOVER for the showcase, not in code comments next to the hash.

### 3. Login + session
- `GET /login` renders an email + password form; `POST /login` authenticates via
  the `Authenticator`. Success sets the session and redirects to `/`; failure
  re-renders with a generic "invalid credentials" message (no user enumeration).
- `GET/POST /logout` clears the session.
- Session is a **signed cookie** via Starlette's `SessionMiddleware`, holding
  only `email` and `role`. Signing secret comes from
  `SPRINTSIGHT_SECRET_KEY` (env), with a clearly-labelled dev default so the app
  still runs offline. The dev default is acceptable only because data is
  synthetic and single-tenant; a real deployment must set the env var.

### 4. Gating the existing routes
- A small FastAPI dependency, `current_user(request)`, reads the session.
  - For HTML routes: if anonymous, redirect (303) to `/login`.
  - For API routes: if anonymous, raise `401`.
- A `require_admin` dependency builds on it: non-admin -> `403`.
- The four existing routes adopt `current_user`. New `/admin/accounts` adopts
  `require_admin` and renders the seed user list (email + role only, never hashes
  or passwords).

### Data flow
Browser -> `/login` (POST) -> `Authenticator.authenticate(email, pw)` ->
on success, `SessionMiddleware` writes signed cookie -> subsequent requests carry
the cookie -> `current_user` resolves it -> route renders. No DB, no network.

### Error handling
- Wrong credentials: generic failure, no enumeration, 200 re-render of the form.
- Anonymous on protected route: 303 redirect (HTML) / 401 (API).
- Non-admin on admin route: 403.
- Missing/garbled cookie: treated as anonymous (fail closed).

## Eval-first: tests that define "done"

Auth is enforcement logic, not an LLM behaviour, so the "eval" is a deterministic
test suite (consistent with `tests/web/`). Written before the feature. Asserts:

1. Anonymous `GET /` and `/team/{id}` -> redirect to `/login`.
2. Anonymous `GET /api/portfolio` and `/api/team/{id}` -> `401`.
3. Valid login -> session set -> protected routes return `200`.
4. Wrong password -> rejected, no session, generic message.
5. Logout -> session cleared -> protected routes blocked again.
6. Non-admin (`viewer`, `delivery_manager`) `GET /admin/accounts` -> `403`.
7. Admin `GET /admin/accounts` -> `200`, lists the three seed users, exposes no
   hashes or passwords.
8. Password hashing round-trips (correct verifies, wrong fails); no plain-text at
   rest.
9. Existing Stage 6 service/page/API tests updated to authenticate first and
   still pass (the served-data ground truth is unchanged).

## Security notes (security-first principle)

- No rolling our own crypto beyond stdlib PBKDF2 password hashing with per-user
  salt and a sane iteration count.
- Session holds no secret beyond what the signed cookie protects; signing key is
  env-driven with a dev-only default.
- Fail closed everywhere (missing/invalid session = anonymous).
- Admin view exposes email + role only.
- No new external call and no new persisted real data in this slice (seed users
  are synthetic). New persistence/external-call decisions are explicitly deferred
  to the Supabase wiring step and will be flagged then.

## Learning-queue flag (HANDOVER)

New concept for a non-engineer: **auth seam + session cookie** (why we fake the
identity provider offline the same way we fake the database and the embedder, and
what a "signed session cookie" is). One line to be appended to the HANDOVER
Learning queue at implementation time (flag only; the training thread writes the
log).

## Open items for implementation

- Confirm seed file path/format (`data/users.yaml` vs `sprintsight/web/auth/`).
- Confirm whether `SessionMiddleware` (needs `itsdangerous`) is already pulled in
  by the `web` extra; add it to the extra if not.
- Decide the redirect target after login (default `/`).
