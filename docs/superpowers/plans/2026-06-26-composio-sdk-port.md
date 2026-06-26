# Composio SDK Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the live Jira connector from the removed `ComposioToolSet` API to the current `composio==0.16` `Composio` client so `/crosstool` can show a genuine "live" badge.

**Architecture:** Change only the one network seam (`fetch_issues`). Extract the new response-unwrap into a pure, tested helper. Keep the pure translator/normaliser stable. Make the live gate require the connection id so the offline/live badge stays honest. Re-confirm the inner shape live as a final human-run step.

**Tech Stack:** Python 3.12, `composio==0.16` (new `Composio` client), `PyGithub`, FastAPI, pytest.

## Global Constraints

- Read-only. No writes to Jira or GitHub.
- Offline-by-default and deterministic in CI. No network in any test. Live Composio paths are never exercised in CI.
- Deterministic eval gates (watermelon 4/4, report 4/4, cross-tool 7/7) stay the only CI gate and stay untouched.
- New runtime secret is read from the environment, never committed: `COMPOSIO_CONNECTED_ACCOUNT_ID` (a connection id, not a token). `COMPOSIO_API_KEY` already required.
- No em dashes in any David-facing text.
- Spec: `docs/superpowers/specs/2026-06-26-composio-sdk-port-design.md`.

---

### Task 1: Pure response-unwrap helper `_issues_from_response`

The one genuinely new piece of logic: pull the issue list out of the new `ToolExecutionResponse`, raising on a failed call so the caller's fail-safe gate falls back to offline. Pure, so fully unit-tested with no network.

**Files:**
- Modify: `sprintsight/connect/connector.py` (add helper; add `import os` for Task 2 use is deferred to Task 2)
- Test: `tests/test_connect.py`

**Interfaces:**
- Produces: `_issues_from_response(resp: Any) -> list[dict[str, Any]]` — returns `resp.data["issues"]` on success; raises `RuntimeError` when `resp.successful` is False; returns `[]` when data/issues are missing.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_connect.py` (import the helper in the existing import line from `sprintsight.connect.connector`):

```python
from sprintsight.connect.connector import _issues_from_response


class _Resp:
    def __init__(self, successful=True, data=None, error=None):
        self.successful = successful
        self.data = data
        self.error = error


def test_issues_from_response_returns_issue_list():
    resp = _Resp(data={"issues": [{"key": "SSSB-1"}, {"key": "SSSB-2"}]})
    issues = _issues_from_response(resp)
    assert [i["key"] for i in issues] == ["SSSB-1", "SSSB-2"]


def test_issues_from_response_raises_on_failure():
    import pytest
    resp = _Resp(successful=False, error="boom")
    with pytest.raises(RuntimeError, match="boom"):
        _issues_from_response(resp)


def test_issues_from_response_empty_when_no_issues():
    assert _issues_from_response(_Resp(data={})) == []
    assert _issues_from_response(_Resp(data=None)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_connect.py -k issues_from_response -v`
Expected: FAIL with `ImportError`/`AttributeError` (helper not defined).

- [ ] **Step 3: Write the helper**

In `sprintsight/connect/connector.py`, above `fetch_issues`:

```python
def _issues_from_response(resp: Any) -> list[dict[str, Any]]:
    """Pull the issue list out of a Composio ToolExecutionResponse, raising on a failed
    call so the caller's fail-safe gate can fall back to offline. `data` is already the
    tool's data dict in the new SDK (no outer envelope)."""
    if not getattr(resp, "successful", True):
        raise RuntimeError(
            f"Composio JIRA_SEARCH_ISSUES failed: {getattr(resp, 'error', None)}"
        )
    data = getattr(resp, "data", resp) or {}
    return data.get("issues", []) or []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_connect.py -k issues_from_response -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/connect/connector.py tests/test_connect.py
git commit -m "feat(stage7): pure Composio response-unwrap helper [SS-5]"
```

---

### Task 2: Rewrite `fetch_issues` against the new `Composio` client + pin + doc

Swap the removed `ComposioToolSet().execute_action(...)` for `Composio().tools.execute(...)`, identify the account by `COMPOSIO_CONNECTED_ACCOUNT_ID`, and delegate unwrapping to Task 1's helper. Pin the SDK so the targeted API is the one that installs. Update the live-run doc.

**Files:**
- Modify: `sprintsight/connect/connector.py:38-61` (`fetch_issues`, add `import os` at top)
- Modify: `pyproject.toml` (connectors extra)
- Modify: `docs/connectors/live-run.md` (live Jira command)
- Test: `tests/test_connect.py`

**Interfaces:**
- Consumes: `_issues_from_response` (Task 1), `_to_clean` (existing).
- Produces: `fetch_issues(project_key: str) -> list[dict[str, Any]]` — unchanged signature, so the injectable `fetcher` seam on `JiraConnector` is untouched.

- [ ] **Step 1: Write the failing wiring test**

This pins that `fetch_issues` builds the new client, passes the connection id from the env, and routes the result through the helper. Inject a fake `composio` module so no network is touched.

Add to `tests/test_connect.py`:

```python
def test_fetch_issues_uses_new_client_and_connection_id(monkeypatch):
    import sys
    import types

    calls = {}

    class _FakeTools:
        def execute(self, slug, arguments, **kwargs):
            calls["slug"] = slug
            calls["arguments"] = arguments
            calls["connected_account_id"] = kwargs.get("connected_account_id")

            class _R:
                successful = True
                data = {"issues": [{"key": "SSSB-7", "summary": "x", "status": "To Do"}]}
                error = None

            return _R()

    class _FakeComposio:
        def __init__(self, *a, **k):
            self.tools = _FakeTools()

    fake_mod = types.ModuleType("composio")
    fake_mod.Composio = _FakeComposio
    monkeypatch.setitem(sys.modules, "composio", fake_mod)
    monkeypatch.setenv("COMPOSIO_API_KEY", "k")
    monkeypatch.setenv("COMPOSIO_CONNECTED_ACCOUNT_ID", "ac_test")

    from sprintsight.connect.connector import fetch_issues

    issues = fetch_issues("SSSB")
    assert calls["slug"] == "JIRA_SEARCH_ISSUES"
    assert calls["connected_account_id"] == "ac_test"
    assert "project = SSSB" in calls["arguments"]["jql"]
    assert issues[0]["key"] == "SSSB-7"  # routed through _to_clean
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_connect.py -k fetch_issues_uses_new_client -v`
Expected: FAIL (current `fetch_issues` imports `ComposioToolSet`, which the fake module does not define -> `ImportError`/`AttributeError`).

- [ ] **Step 3: Rewrite `fetch_issues`**

Add `import os` to the top of `sprintsight/connect/connector.py` (after `import json`). Replace the body of `fetch_issues` (lines ~49-61) with:

```python
    from composio import Composio  # lazy: runtime-only dependency

    composio = Composio()  # reads COMPOSIO_API_KEY from the environment
    resp = composio.tools.execute(
        "JIRA_SEARCH_ISSUES",
        arguments={
            "jql": f"project = {project_key} ORDER BY updated DESC",
            "fields": ["summary", "status", "labels", "description", "updated", "assignee"],
            "max_results": 100,
        },
        connected_account_id=os.environ["COMPOSIO_CONNECTED_ACCOUNT_ID"],
    )
    return [_to_clean(issue) for issue in _issues_from_response(resp)]
```

Update the docstring's stale line about `ComposioToolSet` to name the `Composio` client and the `COMPOSIO_CONNECTED_ACCOUNT_ID` env var.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_connect.py -k fetch_issues_uses_new_client -v`
Expected: PASS.

- [ ] **Step 5: Pin the SDK and update the live-run doc**

In `pyproject.toml`, change the connectors extra entry `"composio",` to:

```toml
  "composio>=0.16,<0.17",
```

In `docs/connectors/live-run.md`, update the "Live Jira read" section so the export block reads:

```
    export COMPOSIO_API_KEY=<your-composio-key>
    export COMPOSIO_CONNECTED_ACCOUNT_ID=<your-ac_... connection id>
    python scripts/run_connector_demo.py --project SSSB
```

and add one sentence: "The connection id identifies which connected Jira account Composio reads; the connector reads it from `COMPOSIO_CONNECTED_ACCOUNT_ID` and never commits it."

- [ ] **Step 6: Run the full connector suite**

Run: `.venv/bin/python -m pytest tests/test_connect.py -v`
Expected: PASS (including the unchanged `test_to_clean_maps_real_composio_shape` and `test_jira_connector_uses_injected_fetcher`).

- [ ] **Step 7: Commit**

```bash
git add sprintsight/connect/connector.py tests/test_connect.py pyproject.toml docs/connectors/live-run.md
git commit -m "feat(stage7): port fetch_issues to the current Composio client [SS-5]"
```

---

### Task 3: Honest live gate requires the connection id

Extend the `/crosstool` live gate so it only attempts a live read when the connection id is present too. A config gap then shows plain "offline" instead of the misleading "offline (live read failed)".

**Files:**
- Modify: `sprintsight/web/crosstool_service.py:112-120` (`_crosstool_live_enabled`)
- Test: `tests/web/test_crosstool_service.py:111-141`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_crosstool_live_enabled()` returns True only when `SPRINTSIGHT_CROSSTOOL_LIVE==on` AND `GITHUB_TOKEN` AND `COMPOSIO_API_KEY` AND `COMPOSIO_CONNECTED_ACCOUNT_ID` AND repo AND project are all present.

- [ ] **Step 1: Update the gate test to expect six credentials**

In `tests/web/test_crosstool_service.py`, add the new key to `_ALL_LIVE_ENV`:

```python
_ALL_LIVE_ENV = {
    "SPRINTSIGHT_CROSSTOOL_LIVE": "on",
    "GITHUB_TOKEN": "x",
    "COMPOSIO_API_KEY": "x",
    "COMPOSIO_CONNECTED_ACCOUNT_ID": "ac_x",
    "SPRINTSIGHT_CROSSTOOL_REPO": "owner/repo",
    "SPRINTSIGHT_CROSSTOOL_PROJECT": "SSSB",
}
```

Add `"COMPOSIO_CONNECTED_ACCOUNT_ID"` to the `@pytest.mark.parametrize("omitted", [...])` list (before `None`). Rename the test to `test_live_gate_requires_all_six_credentials` and update its docstring to say "six".

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/web/test_crosstool_service.py -k live_gate_requires -v`
Expected: FAIL for the `COMPOSIO_CONNECTED_ACCOUNT_ID` case (gate still returns True without it).

- [ ] **Step 3: Extend the gate**

In `sprintsight/web/crosstool_service.py`, in `_crosstool_live_enabled()`, add the connection-id check:

```python
def _crosstool_live_enabled() -> bool:
    """True only when the live switch is deliberately on AND every credential and the
    repo/project are present (fail-safe). Any missing piece falls back to offline."""
    return (
        os.environ.get(_LIVE_FLAG) == "on"
        and bool(os.environ.get("GITHUB_TOKEN"))
        and bool(os.environ.get("COMPOSIO_API_KEY"))
        and bool(os.environ.get("COMPOSIO_CONNECTED_ACCOUNT_ID"))
        and _crosstool_config() is not None
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/web/test_crosstool_service.py -k live_gate_requires -v`
Expected: PASS (now 7 parametrized cases).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/crosstool_service.py tests/web/test_crosstool_service.py
git commit -m "feat(stage7): honest live gate requires the Composio connection id [SS-5]"
```

---

### Task 4: Full suite + ruff green, learning-queue flag

**Files:**
- Modify: `HANDOVER.md` (Learning queue line)

- [ ] **Step 1: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (prior 240 passed + 3 skipped, plus the 4 new tests = 244 passed + 3 skipped; the renamed gate test gains one parametrized case).

- [ ] **Step 2: Lint**

Run: `.venv/bin/ruff check .`
Expected: clean.

- [ ] **Step 3: Add the learning-queue flag**

Append one line to the `Learning queue` section in `HANDOVER.md`:

```
SDK version drift | code written against an old third-party SDK breaks when a newer rewritten version installs; fix is to target + pin the current API | sprintsight/connect/connector.py + 2026-06-26 | 2026-06-26
```

- [ ] **Step 4: Commit**

```bash
git add HANDOVER.md
git commit -m "docs(stage7): learning-queue flag for the Composio SDK port [SS-5]"
```

---

## Live calibration (human-run, AFTER the branch is reviewed; not a CI step)

Walked one command at a time in David's terminal with real credentials. This confirms the
assumed `data["issues"]` key and the inner issue shape against the real board. If reality
differs, adjust `_issues_from_response` / `_to_clean` and their fixtures, then re-run the suite.

1. `export COMPOSIO_API_KEY=<david's key>`
2. `export COMPOSIO_CONNECTED_ACCOUNT_ID=<david's ac_... id>`
3. `python scripts/run_connector_demo.py --project SSSB`
4. Confirm real SSSB tickets print as cited evidence.
5. Then the full `/crosstool` live demo (set the six gate vars incl. `GITHUB_TOKEN`, launch the
   web app, log in as `admin@sprintsight.test`, open `/crosstool`, confirm the badge reads "live").
