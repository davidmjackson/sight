# Switching the app to the least-privilege `app_rw` role (slice 7)

Plain-English: slice 6 added the per-tenant database rule (RLS), but it does not apply to the
`postgres` owner the app currently logs in as. This is the step that finally turns isolation on:
create a normal, least-privilege login (`app_rw`) and point the app at it.

## What CI already proves
The CI `db` job creates `app_rw`, runs ingest + retrieval **as** `app_rw`, and asserts it is subject
to RLS (0 rows with no tenant set, the tenant's rows with one). So the role, grants, and policy are
verified. Only the live Supabase switch below is manual.

## One-time live setup (operator)

Migration `0004_app_role.sql` already created `app_rw` (NOLOGIN, no password) and granted it least
privilege when you ran the migrations. Two manual steps remain on the live database.

1. Give `app_rw` a login + a strong password. In the Supabase SQL editor (connected as the admin),
   run (substitute a real generated secret, do not reuse this placeholder):

   `alter role app_rw with login password 'PUT_A_STRONG_GENERATED_SECRET_HERE';`

2. Repoint the app at `app_rw`. In the app's `.env`, change `DATABASE_URL` so the username is
   `app_rw` and the password is the secret from step 1, keeping the **session pooler** host/port
   (IPv4; the transaction pooler does not carry session GUCs, which would make every query return
   zero rows). Example shape:

   `DATABASE_URL=postgresql://app_rw:<secret>@aws-0-<region>.pooler.supabase.com:5432/postgres`

   (Migrations still run as the admin/owner; only the running app uses `app_rw`.)

## Verify live
- A fresh app process can ingest + retrieve (it sets `app.tenant_id` on connect).
- `select rolsuper or rolbypassrls from pg_roles where rolname='app_rw';` returns `f`.
- As `app_rw` with no tenant set, `select count(*) from team;` returns 0 (fail-closed); with
  `set app.tenant_id = '<demo-uuid>';` first, it returns the tenant's rows.

## Notes
- Keep the `app_rw` password only in the deploy secret store (`.env` / Supabase), never in git.
- The RLS policy applies to PUBLIC (slice 6), so the PostgREST anon/authenticated roles still get
  zero rows (they cannot set the GUC). We intentionally did NOT scope the policy `TO app_rw`, which
  would lock the admin/owner out of its own tables.
- Deploy ORDER if re-applying from scratch: the GUC-setting app code must be live before the
  RLS-policy migration (0003), else connections fail closed until redeploy.
