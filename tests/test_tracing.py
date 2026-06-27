"""Langfuse tracing is OPT-IN: it must stay off unless deliberately enabled.

Cost control + consistency with the project's other integrations (LLM/DB/crosstool/embedder all
need an explicit flag AND credentials). With the keys present in a developer's .env, routine eval/
graph runs must still send ZERO events to Langfuse unless SPRINTSIGHT_TRACE=on.
"""

from sprintsight.evals.tracing import NoOpTracer, _enabled, get_tracer

KEYS = {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}


def _set(monkeypatch, **env):
    for k in ("SPRINTSIGHT_TRACE", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_disabled_by_default_even_with_keys(monkeypatch):
    _set(monkeypatch, **KEYS)  # keys present, no flag -> still off
    assert _enabled() is False
    assert isinstance(get_tracer(), NoOpTracer)


def test_flag_on_but_no_keys_stays_off(monkeypatch):
    _set(monkeypatch, SPRINTSIGHT_TRACE="on")
    assert _enabled() is False
    assert isinstance(get_tracer(), NoOpTracer)


def test_flag_on_missing_one_key_stays_off(monkeypatch):
    _set(monkeypatch, SPRINTSIGHT_TRACE="on", LANGFUSE_PUBLIC_KEY="pk")
    assert _enabled() is False


def test_enabled_only_with_flag_and_both_keys(monkeypatch):
    _set(monkeypatch, SPRINTSIGHT_TRACE="on", **KEYS)
    assert _enabled() is True
