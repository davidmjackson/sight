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
