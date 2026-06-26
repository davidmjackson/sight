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

    try:
        import psycopg  # lazy: only needed when actually applying
    except ImportError:
        print("psycopg not installed; run: pip install -e '.[db]'")
        return 3

    files = migration_files()
    current_file: str | None = None
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            for f in files:
                current_file = f.name
                print(f"applying {f.name}")
                conn.execute(f.read_text(encoding="utf-8"))
    except psycopg.Error as exc:
        where = f" at {current_file}" if current_file else ""
        print(
            f"migrate failed{where} ({type(exc).__name__}: {exc}). "
            f"migrate.py is a ONE-TIME step; the database may already be migrated. "
            f"Re-running after the schema exists will fail."
        )
        return 4
    print(f"RESULT applied {len(files)} migration(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
