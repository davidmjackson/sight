# Persistent Supabase (real-wiring slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a normal (non-CI) run find its database config via a fail-safe `.env` loader, and persist the synthetic corpus into a real Supabase Postgres + pgvector instance, proven to survive a restart.

**Architecture:** The database code path (`PostgresStore`, `PostgresRetriever`, `db/migrations/`, `scripts/ingest.py`, `scripts/retrieve_smoke.py`) already exists and is CI-tested against a local pgvector container. This slice adds the one missing piece, a stdlib `.env` loader, wires it into the three entry points, adds a tiny `psycopg`-based migration runner so no separate `psql` client is needed, documents the provisioning runbook, and live-verifies a real Supabase load. The web screens still read corpus files (unchanged).

**Tech Stack:** Python 3.11, FastAPI, psycopg 3 (the `[db]` extra, lazy-imported), pgvector, pytest.

## Global Constraints

- NO new dependencies. The loader is a stdlib parser (~20 lines), not `python-dotenv`.
- The loader MUST NOT override variables already present in `os.environ` (real `export` and CI win).
- The loader MUST NOT print or log values (no secret leakage).
- Data stays SYNTHETIC; still `HashingEmbedder` (no real embedding model this slice).
- Deterministic eval gates stay the CI gate and MUST remain green: watermelon 4/4, report 4/4, cross-tool 7/7.
- The CI `db` job is unchanged; it stays the proof of the persistence logic.
- David-facing docs: plain English, define acronyms on first use, NO em dashes.
- Frequent commits: one per task.

---

### Task 1: The `.env` loader

**Files:**
- Create: `sprintsight/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_env(path: str | os.PathLike[str] = ".env") -> None` in `sprintsight.config`. Reads simple `KEY=value` lines from the file into `os.environ` without overriding existing keys; no-op when the file is absent; never prints values.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import os

import pytest

from sprintsight.config import load_env


@pytest.fixture(autouse=True)
def _restore_env():
    """Snapshot os.environ and restore it after each test (load_env writes to it directly)."""
    saved = dict(os.environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _write(tmp_path, text):
    p = tmp_path / ".env"
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_key_value(tmp_path):
    os.environ.pop("SP_TEST_KEY", None)
    p = _write(tmp_path, "SP_TEST_KEY=hello\n")
    load_env(p)
    assert os.environ["SP_TEST_KEY"] == "hello"


def test_does_not_override_existing(tmp_path):
    os.environ["SP_TEST_KEY"] = "original"
    p = _write(tmp_path, "SP_TEST_KEY=fromfile\n")
    load_env(p)
    assert os.environ["SP_TEST_KEY"] == "original"


def test_absent_file_is_noop(tmp_path):
    missing = tmp_path / "nope.env"
    load_env(missing)  # must not raise


def test_ignores_comments_blanks_and_strips_quotes(tmp_path):
    os.environ.pop("SP_TEST_QUOTED", None)
    p = _write(tmp_path, "\n# a comment\nSP_TEST_QUOTED=\"spaced value\"\n")
    load_env(p)
    assert os.environ["SP_TEST_QUOTED"] == "spaced value"


def test_never_prints_value(tmp_path, capsys):
    os.environ.pop("SP_TEST_SECRET", None)
    p = _write(tmp_path, "SP_TEST_SECRET=swordfish\n")
    load_env(p)
    out = capsys.readouterr()
    assert "swordfish" not in out.out
    assert "swordfish" not in out.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.config'`

- [ ] **Step 3: Write the minimal implementation**

```python
# sprintsight/config.py
"""Minimal .env loader for non-CI runs (no python-dotenv dependency).

The project deliberately has no autoloader; this fills that gap for local and live runs while
keeping CI and real exports authoritative. load_env() reads simple KEY=value lines from a .env
file into os.environ WITHOUT overriding variables already set, and is a no-op when the file is
absent. It never prints values.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | os.PathLike[str] = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check sprintsight/config.py tests/test_config.py
git add sprintsight/config.py tests/test_config.py
git commit -m "feat(config): fail-safe .env loader (no override, no secret leak) [SS-5]"
```

---

### Task 2: Wire `load_env` into the three entry points

**Files:**
- Modify: `sprintsight/web/app.py` (add import; call `load_env()` as the FIRST line of `create_app()`, before `session_secret()` is read)
- Modify: `scripts/ingest.py` (add import; call `load_env()` as the first line of `main()`)
- Modify: `scripts/retrieve_smoke.py` (add import; call `load_env()` as the first line of `main()`)
- Test: `tests/test_env_wiring.py`

**Interfaces:**
- Consumes: `load_env` from `sprintsight.config` (Task 1).
- Produces: nothing new; entry points now self-load `.env`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_env_wiring.py
import os

import pytest


def test_create_app_calls_load_env(monkeypatch):
    calls = []
    monkeypatch.setattr("sprintsight.web.app.load_env", lambda *a, **k: calls.append(True))
    from sprintsight.web.app import create_app

    create_app()
    assert calls, "create_app must call load_env() at startup"


def test_ingest_main_calls_load_env(monkeypatch):
    calls = []
    monkeypatch.setattr("scripts.ingest.load_env", lambda *a, **k: calls.append(True))
    monkeypatch.delenv("DATABASE_URL", raising=False)  # forces the in-memory store path
    import scripts.ingest as ingest

    rc = ingest.main()
    assert calls, "ingest.main must call load_env()"
    assert rc == 0


def test_retrieve_smoke_main_calls_load_env(monkeypatch):
    calls = []
    monkeypatch.setattr("scripts.retrieve_smoke.load_env", lambda *a, **k: calls.append(True))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import scripts.retrieve_smoke as smoke

    rc = smoke.main()
    assert calls, "retrieve_smoke.main must call load_env()"
    assert rc == 2  # no DATABASE_URL -> early clean exit (after load_env)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_env_wiring.py -v`
Expected: FAIL (`AttributeError` on `sprintsight.web.app.load_env` / `scripts.ingest.load_env` — the names are not imported yet)

- [ ] **Step 3: Wire `app.py`**

Add to the imports block of `sprintsight/web/app.py`:

```python
from sprintsight.config import load_env
```

Make `load_env()` the first statement inside `create_app()`:

```python
def create_app() -> FastAPI:
    load_env()
    app = FastAPI(title="Sprintsight watermelon detector")
```

- [ ] **Step 4: Wire `scripts/ingest.py`**

Add the import near the other imports:

```python
from sprintsight.config import load_env
```

Make `load_env()` the first line of `main()`:

```python
def main() -> int:
    load_env()
    dsn = os.getenv("DATABASE_URL")
```

- [ ] **Step 5: Wire `scripts/retrieve_smoke.py`**

Add the import near the other imports:

```python
from sprintsight.config import load_env
```

Make `load_env()` the first line of `main()`:

```python
def main() -> int:
    load_env()
    dsn = os.getenv("DATABASE_URL")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_env_wiring.py -v`
Expected: PASS (3 passed). Note: `test_ingest_main_calls_load_env` runs a real in-memory ingest of the 37-artifact corpus, so it takes a second or two.

- [ ] **Step 7: Lint and commit**

```bash
.venv/bin/ruff check sprintsight/web/app.py scripts/ingest.py scripts/retrieve_smoke.py tests/test_env_wiring.py
git add sprintsight/web/app.py scripts/ingest.py scripts/retrieve_smoke.py tests/test_env_wiring.py
git commit -m "feat: auto-load .env at web app + DB script entry points [SS-5]"
```

---

### Task 3: `scripts/migrate.py` migration runner

**Files:**
- Create: `scripts/migrate.py`
- Test: `tests/test_migrate.py`

**Interfaces:**
- Consumes: `load_env` from `sprintsight.config` (Task 1).
- Produces: `migration_files(directory: Path = _MIGRATIONS) -> list[Path]` (pure; returns `*.sql` sorted by filename) and `main() -> int` (applies them against `DATABASE_URL` via lazy psycopg; returns 2 if `DATABASE_URL` is unset).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_migrate.py
from pathlib import Path


def test_migration_files_sorted_sql_only(tmp_path):
    from scripts.migrate import migration_files

    (tmp_path / "0002_b.sql").write_text("select 2;", encoding="utf-8")
    (tmp_path / "0001_a.sql").write_text("select 1;", encoding="utf-8")
    (tmp_path / "0010_c.sql").write_text("select 10;", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")

    names = [p.name for p in migration_files(tmp_path)]
    assert names == ["0001_a.sql", "0002_b.sql", "0010_c.sql"]


def test_main_returns_2_without_database_url(monkeypatch, capsys):
    import scripts.migrate as migrate

    monkeypatch.setattr(migrate, "load_env", lambda *a, **k: None)  # don't read the repo .env
    monkeypatch.delenv("DATABASE_URL", raising=False)

    rc = migrate.main()
    out = capsys.readouterr().out
    assert rc == 2
    assert "DATABASE_URL not set" in out


def test_real_migrations_discovered():
    """The real db/migrations dir has at least the init migration, in order."""
    from scripts.migrate import migration_files

    files = migration_files()
    assert files, "expected at least one migration file"
    assert files == sorted(files)
    assert all(p.suffix == ".sql" for p in files)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_migrate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.migrate'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/migrate.py
"""Apply db/migrations/*.sql in filename order against DATABASE_URL.

Reuses psycopg (the [db] extra) so provisioning needs no separate psql client. psycopg is
lazy-imported so importing this module does not require the extra. psycopg's execute() runs a
multi-statement script when no parameters are passed (simple query protocol). Run after
setting DATABASE_URL; see docs/db/supabase-setup.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sprintsight.config import load_env

_MIGRATIONS = Path(__file__).resolve().parents[1] / "db" / "migrations"


def migration_files(directory: Path = _MIGRATIONS) -> list[Path]:
    """Return *.sql files sorted by filename (the apply order). Pure."""
    return sorted(Path(directory).glob("*.sql"))


def main() -> int:
    load_env()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set; see docs/db/supabase-setup.md")
        return 2

    import psycopg  # lazy: only needed when actually applying

    files = migration_files()
    with psycopg.connect(dsn, autocommit=True) as conn:
        for f in files:
            print(f"applying {f.name}")
            conn.execute(f.read_text(encoding="utf-8"))
    print(f"RESULT applied {len(files)} migration(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_migrate.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check scripts/migrate.py tests/test_migrate.py
git add scripts/migrate.py tests/test_migrate.py
git commit -m "feat(migrate): psycopg migration runner (no psql client needed) [SS-5]"
```

---

### Task 4: Provisioning runbook `docs/db/supabase-setup.md`

**Files:**
- Create: `docs/db/supabase-setup.md`

**Interfaces:** none (documentation). Mirrors the style of `docs/connectors/live-run.md`.

- [ ] **Step 1: Write the runbook**

Write `docs/db/supabase-setup.md` with exactly these sections and content (plain English, no em dashes):

```markdown
# Running Sprintsight against a real Supabase database

Plain-English summary: the app's database code is tested fully offline (CI uses a throwaway
Postgres container). To run it against a real, always-on database you create a Supabase project
(Supabase is a managed cloud Postgres provider), put its connection string in a local .env file,
then run three commands: migrate, ingest, and a read-back check. Everything here uses SYNTHETIC
data. No real customer data is involved.

## One-time setup

Install the database extra editable, so the scripts run your working tree:

    pip install -e '.[db]'

## Provision (you do this once; it needs your account)

1. Create a Supabase project in a UK or EU region (residency, per ADR-0002).
2. In the SQL editor or Database settings, enable the `pgvector` extension (it stores the
   embedding vectors used for semantic search).
3. Copy the database connection string (the "URI" form, starting `postgresql://`). Make sure it
   requires TLS by appending `?sslmode=require` if it is not already there.
4. Put it in a local `.env` file at the repo root (this file is gitignored, never committed):

       DATABASE_URL=postgresql://...your-connection-string...?sslmode=require

   The app auto-loads `.env`. A real `export DATABASE_URL=...` in your terminal still wins over
   the file, and CI is unaffected.

## Load (run these three, in order, from the repo root)

    python scripts/migrate.py          # apply the schema
    python scripts/ingest.py           # load the 37-artifact synthetic corpus
    python scripts/retrieve_smoke.py   # a fresh process reads a cited chunk back

Expected: `migrate.py` prints `RESULT applied 1 migration(s)`; `ingest.py` prints a `RESULT`
line with `"db_artifact": 37`; `retrieve_smoke.py` exits 0 and prints ranked results with
provenance. Because `retrieve_smoke.py` is a separate process from `ingest.py`, a successful
read proves the data persisted and survives a restart.

## Re-running is safe

`ingest.py` is idempotent (keyed on a content hash). A second run reports `"ingested": 0` and
skips the existing rows, so you can re-run it without duplicating data.

## Security notes

- Synthetic data only; encryption-at-rest is provided by Supabase (ADR-0002).
- `DATABASE_URL` holds your database password. It lives only in `.env` (gitignored) and is never
  logged. Check it is set without printing it: `python -c "import os;print('set' if os.getenv('DATABASE_URL') else 'MISSING')"`.
- Require TLS (`sslmode=require`).
- A dedicated least-privilege database role is a documented follow-on (the first load may use the
  default role).
```

- [ ] **Step 2: Commit**

```bash
git add docs/db/supabase-setup.md
git commit -m "docs(db): Supabase provisioning + load runbook [SS-5]"
```

---

### Task 5: Live verification (human-in-the-loop) + closeout

**Files:** none (this is the live proof + state updates). NOT an automated test; it is the real-database equivalent of the connector live verification.

**Interfaces:** none.

- [ ] **Step 1: Full offline suite green before live work**

Run: `.venv/bin/pytest -q`
Expected: all pass + 3 skipped (the new loader/wiring/migrate tests included). Also run the eval gates:
`.venv/bin/python scripts/run_watermelon_eval.py` (4/4) and `.venv/bin/python scripts/run_report_eval.py` (4/4).

- [ ] **Step 2: David provisions Supabase**

Walk David through `docs/db/supabase-setup.md` one command at a time (per the global shell-walkthrough rules): create the project (UK/EU), enable pgvector, put `DATABASE_URL` in `.env`. Confirm it is set with the length/presence check (never print the value).

- [ ] **Step 3: Apply the migration**

Run (David's terminal): `python scripts/migrate.py`
Expected: `applying 0001_init.sql` then `RESULT applied 1 migration(s)`.

- [ ] **Step 4: Load the corpus**

Run: `python scripts/ingest.py`
Expected: a `RESULT` line containing `"db_artifact": 37` and non-zero chunk counts.

- [ ] **Step 5: Prove restart-survival**

Run: `python scripts/retrieve_smoke.py`
Expected: exit 0 with ranked results carrying provenance (a separate process reading the data
back proves persistence).

- [ ] **Step 6: Update state + board**

- Update `HANDOVER.md` ("Where we are") and project memory with the slice outcome and the live-verified result.
- Log a new Jira Story under Epic SS-5 via the Composio MCP, walked through the board states per `docs/jira/workflow.md`, with a completion comment.
- Confirm `.env` is still gitignored and not staged.

---

## Self-Review

**Spec coverage:**
- `.env` loader (spec 2a) -> Task 1 + wiring Task 2. Covered.
- `scripts/migrate.py` (spec 2b step 2) -> Task 3. Covered.
- Provisioning runbook (spec 2b, `docs/db/supabase-setup.md`) -> Task 4. Covered.
- Migrate/ingest/retrieve against real Supabase + restart proof (spec 2b steps 1-4, DoD) -> Task 5. Covered.
- Eval-first / loader tests (spec 2c) -> Task 1 + Task 3 tests, written before implementation. Covered.
- CI `db` job unchanged; deterministic gates unchanged (spec 2c) -> Global Constraints + Task 5 step 1. Covered.
- Security flags (spec 2d) -> runbook security notes (Task 4) + Global Constraints. Covered.
- Out-of-scope items (web read path, real embedder, auth/CSRF, team_id) -> not touched by any task. Correct.

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output. Clean.

**Type consistency:** `load_env(path=...)` signature identical in Task 1, 2, 3. `migration_files(directory=...)` and `main() -> int` consistent across Task 3 and its tests. Patch targets (`sprintsight.web.app.load_env`, `scripts.ingest.load_env`, `scripts.retrieve_smoke.load_env`) match the imports added in Task 2. Consistent.
