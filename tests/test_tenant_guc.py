"""Slice 6 — the stores must announce their tenant to the DB on connect (RLS GUC). Eval-first.

RLS enforcement itself needs real Postgres (CI `db` job + db/checks/rls_isolation.sql). These
offline tests pin the APP side: both Postgres-backed stores must set the `app.tenant_id` session
GUC immediately after connecting, so every query/insert is tenant-scoped by the database.

psycopg lives only in the optional `[db]` extra, which the offline `lint-and-test` CI job does NOT
install. The stores import psycopg lazily, so we inject a FAKE `psycopg` module into sys.modules
(no real psycopg, no real DB needed) — this runs identically with or without psycopg installed.
"""

import sys
import types

import pytest

from sprintsight.ingest.store import DEMO_TENANT_ID, PostgresStore
from sprintsight.retrieval.postgres import PostgresRetriever


class FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return None

    def cursor(self, *a, **k):  # pragma: no cover - no query runs during __init__
        raise AssertionError("no query should run during __init__")

    def close(self):
        pass


@pytest.fixture
def fake_connect(monkeypatch):
    conns: list[FakeConn] = []

    def _connect(*a, **k):
        c = FakeConn()
        conns.append(c)
        return c

    fake = types.ModuleType("psycopg")
    fake.connect = _connect
    monkeypatch.setitem(sys.modules, "psycopg", fake)
    return conns


def _guc_calls(conn: FakeConn) -> list[tuple[str, object]]:
    return [c for c in conn.calls if "set_config" in c[0] and "app.tenant_id" in c[0]]


def test_store_sets_tenant_guc_on_connect(fake_connect):
    PostgresStore("postgresql://stub")
    calls = _guc_calls(fake_connect[0])
    assert calls, "PostgresStore must set the app.tenant_id GUC on connect"
    assert calls[0][1] == (DEMO_TENANT_ID,)


def test_retriever_sets_tenant_guc_on_connect(fake_connect):
    PostgresRetriever("postgresql://stub")
    calls = _guc_calls(fake_connect[0])
    assert calls, "PostgresRetriever must set the app.tenant_id GUC on connect"
    assert calls[0][1] == (DEMO_TENANT_ID,)


def test_store_guc_uses_the_given_tenant(fake_connect):
    other = "00000000-0000-0000-0000-0000000000ff"
    PostgresStore("postgresql://stub", tenant_id=other)
    assert _guc_calls(fake_connect[0])[0][1] == (other,)
