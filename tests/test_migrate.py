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


def test_main_returns_3_when_psycopg_missing(monkeypatch, capsys):
    """Missing [db] extra yields rc=3 with install hint, no traceback."""
    import sys

    import scripts.migrate as migrate

    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy/dummy")
    monkeypatch.setattr(migrate, "load_env", lambda *a, **k: None)
    # Setting a key to None in sys.modules causes `import psycopg` to raise ImportError.
    monkeypatch.setitem(sys.modules, "psycopg", None)

    rc = migrate.main()
    out = capsys.readouterr().out
    assert rc == 3
    assert "pip install -e '.[db]'" in out


def test_main_returns_4_on_apply_error(monkeypatch, capsys):
    """A psycopg error during apply yields rc=4 with a clean message, no raw traceback."""
    import sys
    import types

    import scripts.migrate as migrate

    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy/dummy")
    monkeypatch.setattr(migrate, "load_env", lambda *a, **k: None)

    # Build a minimal fake psycopg module so connect raises a psycopg-shaped error.
    class FakeError(Exception):
        pass

    class FakeOperationalError(FakeError):
        pass

    def fake_connect(*a, **k):
        raise FakeOperationalError("boom")

    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.Error = FakeError
    fake_psycopg.OperationalError = FakeOperationalError
    fake_psycopg.connect = fake_connect
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    rc = migrate.main()
    out = capsys.readouterr().out
    assert rc == 4
    assert "ONE-TIME" in out
    assert "already be migrated" in out
