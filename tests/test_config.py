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
