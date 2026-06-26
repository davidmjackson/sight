-- Sprintsight migration 0002 — enable Row Level Security (security hardening)
-- Closes the Supabase Security Advisor finding: "Table public.<t> is public, but RLS has
-- not been enabled." Supabase exposes the public schema via PostgREST (reachable with the
-- public anon key). With no RLS, the anon/authenticated roles could read these tables.
--
-- We enable RLS with NO policies on every public table. Effect:
--   * anon / authenticated (the PostgREST API)  -> zero rows (door shut; we do not use the API)
--   * postgres (the table owner; how the app connects) -> unaffected, owners bypass RLS
-- No FORCE ROW LEVEL SECURITY, so the owner keeps full access and the app is untouched.
--
-- Idempotent: ENABLE ROW LEVEL SECURITY is a no-op when already enabled, so this is safe
-- to apply against a database that has already been hardened.

begin;

alter table team              enable row level security;
alter table sprint            enable row level security;
alter table artifact          enable row level security;
alter table chunk             enable row level security;
alter table dependency        enable row level security;
alter table sprint_metric     enable row level security;
alter table burndown_snapshot enable row level security;
alter table signal            enable row level security;

commit;
