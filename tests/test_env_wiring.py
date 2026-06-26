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
