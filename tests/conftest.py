"""Test-wide defaults.

The web auth layer (SS-34) fails safe: it refuses to start without a signing
secret unless explicitly in dev mode. Tests run offline in dev mode, so set the
flag before any app module is imported. setdefault means a real CI/env value
still wins if one is provided.

Hermeticity: `create_app()` runs `load_env()`, which loads the gitignored `.env`
into the process. A developer's `.env` carries a real `DATABASE_URL` (the live
Supabase from real-wiring slice 1), so without this guard the web DB gate
(slice 4) could make a real network call to Supabase during a test run. We pin
`DATABASE_URL` to an unreachable stub BEFORE any app import; `load_env` never
overrides an existing var, so the stub wins. Tests that need a specific value
set it per-test via monkeypatch. The real DB is exercised by CI's `db` job
(scripts, not pytest), never by the suite.
"""

import os

os.environ.setdefault("SPRINTSIGHT_ENV", "dev")
os.environ["DATABASE_URL"] = "postgresql://stub:stub@127.0.0.1:1/sprintsight_tests_no_db"
# Same hermeticity guard for auth: a developer's .env could set SPRINTSIGHT_AUTH=supabase, which
# would make the suite attempt real Supabase logins. Force the offline seed backend (load_env never
# overrides an existing var). Tests that exercise the gate set their own value via monkeypatch.
os.environ["SPRINTSIGHT_AUTH"] = "seed"
