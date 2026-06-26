# Design: port the Jira connector to the current Composio SDK

Date: 2026-06-26
Status: proposed (awaiting review)
Epic: SS-5 (Stage 7, UX Polish + Connectors)
Related: [[stage7-crosstool-live-wire-slice]], docs/connectors/live-run.md

## Plain-English summary (read this first)

Our app can read the live Jira board through Composio (the service that holds the
connection to Jira). The code that does this was written against an OLDER version of
Composio's software kit (SDK). When we installed the connector libraries to run the
live demo, we got the CURRENT Composio SDK, which was rewritten and no longer has the
piece our code calls. So today a live Jira read would throw an error.

The fail-safe we built earlier catches that error, so the page never crashes. But it
falls back to the frozen offline data and shows "offline (live read failed)" instead of
"live". To actually demo live, we have to update the one function that talks to Composio
so it uses the new SDK.

This is a small, contained change. The only network function changes. The well-tested
pure code (the translator and the normaliser) stays the same in shape, and we re-confirm
it against a fresh real sample as the final step. Nothing new is written to Jira; this
stays strictly read-only.

What you (David) will do at the end: paste two secrets into your own terminal (your
Composio API key and your Jira connection id), then we run one command to confirm the
live read works, and finally open the page and watch the badge say "live".

## Problem

`sprintsight/connect/connector.py:fetch_issues` calls:

```python
from composio import ComposioToolSet
toolset = ComposioToolSet()
raw = toolset.execute_action(action="JIRA_SEARCH_ISSUES", params={...})
issues = raw.get("data", {}).get("issues", [])
```

`ComposioToolSet` does not exist in the installed `composio==0.16.0`. The package was
rewritten; it now exposes a `Composio` client. Confirmed by introspection:

- `from composio import ComposioToolSet` raises `ImportError`.
- The module exposes `Composio` instead.
- `Composio().tools.execute(slug, arguments, *, connected_account_id=None, user_id=None, ...)`
  returns a `ToolExecutionResponse` with fields `data: dict`, `error: str | None`,
  `successful: bool`.

So both the call mechanics AND the response envelope changed. The inner Jira issue shape
(flat issue dict, `status`/`reporter` as dicts, `description` as a plain string) is produced
by the same Composio tool (`JIRA_SEARCH_ISSUES`) and is expected to be unchanged, but must be
re-confirmed live.

## Goal

Make `/crosstool` show a genuine "live" badge, reading the real SSSB Jira board through the
current Composio SDK, while keeping the offline-by-default, deterministic-in-CI behaviour and
the fail-safe gate intact.

Out of scope: porting anything beyond the Jira read; new Composio calls; multi-tenant
team_id; persistent storage; the GitHub path (already works with the installed PyGithub).

## Chosen approach (Approach 1: minimal faithful port)

Change only the network seam. Keep the pure, tested code stable. Make the live gate honest.

### 1. Rewrite `fetch_issues` against the new client

```python
def fetch_issues(project_key: str) -> list[dict[str, Any]]:
    from composio import Composio  # lazy: runtime-only dependency

    composio = Composio()  # reads COMPOSIO_API_KEY from env
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

Notes:
- `Composio()` reads `COMPOSIO_API_KEY` from the environment (already a gate requirement).
- The connected account is identified by `COMPOSIO_CONNECTED_ACCOUNT_ID` (David's `ac_...` id),
  read from the environment. No id is hard-coded or committed.
- The function signature is unchanged (`(project_key) -> list[dict]`), so the injectable
  `fetcher` seam on `JiraConnector` and every offline test keep working untouched.

### 2. New pure helper `_issues_from_response` (the eval-first unit)

The one genuinely new piece of logic is unwrapping the new `ToolExecutionResponse`. Extract it
into a pure function so it is tested without a network:

```python
def _issues_from_response(resp: Any) -> list[dict[str, Any]]:
    """Pull the issue list out of a Composio ToolExecutionResponse, raising on a failed call
    so the caller's fail-safe gate can fall back to offline."""
    if not getattr(resp, "successful", True):
        raise RuntimeError(f"Composio JIRA_SEARCH_ISSUES failed: {getattr(resp, 'error', None)}")
    data = getattr(resp, "data", resp) or {}
    return data.get("issues", []) or []
```

This is the slice's red-to-green eval hook: it is written and tested before the live call,
then the exact `data` key is confirmed live (see calibration step) and the test/fixture adjusted
if reality differs.

### 3. Make the live gate honest

In `sprintsight/web/crosstool_service.py`, extend the gate so a missing connection id keeps the
page cleanly offline rather than attempting a live read that is doomed to fail:

- `_crosstool_live_enabled()` additionally requires `COMPOSIO_CONNECTED_ACCOUNT_ID` to be set.
- Result: a config gap shows plain "offline"; only a genuine live failure shows
  "offline (live read failed)".

### 4. Keep `_to_clean` and `normalize` stable, re-pinned live

`_to_clean` and `normalize` are unchanged in shape. The existing
`test_to_clean_maps_real_composio_shape` continues to pin the inner issue mapping. If the live
calibration shows the new SDK returns a different inner shape, `_to_clean` is the single place
that changes, and its test fixture is updated to the real shape.

## Testing (eval-first)

All offline, no network in CI:

1. `_issues_from_response` returns the issue list from a successful response (against a recorded
   new-SDK envelope sample).
2. `_issues_from_response` raises when `successful` is False (so the fail-safe catches it).
3. `_issues_from_response` tolerates a missing/empty `data` (returns `[]`).
4. Existing `test_to_clean_maps_real_composio_shape` stays green (inner mapping unchanged).
5. Existing `test_jira_connector_uses_injected_fetcher` stays green (seam unchanged).
6. New gate test: `_crosstool_live_enabled()` is False when `COMPOSIO_CONNECTED_ACCOUNT_ID` is
   absent even if every other condition is met; True when all are present.

The deterministic watermelon (4/4), report (4/4), and cross-tool (7/7) eval gates stay the only
CI gates and are untouched. Live Composio paths are never exercised in CI.

## Live calibration (final, human-run, David's terminal)

Done once, with David's real credentials, walked one command at a time:

1. `export COMPOSIO_API_KEY=<david's key>`
2. `export COMPOSIO_CONNECTED_ACCOUNT_ID=<david's ac_... id>`
3. `python scripts/run_connector_demo.py --project SSSB` (Jira-only live read)
4. Confirm real SSSB tickets print. Capture the raw response shape; if the `data` key or inner
   issue shape differs from the offline fixture, adjust `_issues_from_response` / `_to_clean` and
   their fixtures, re-run the suite.
5. Then the full live demo: set the five `/crosstool` gate vars (including `GITHUB_TOKEN`), launch
   the web app, log in (`admin@sprintsight.test`), open `/crosstool`, confirm the badge reads
   "live".

## Security

- Read-only. No writes to Jira or GitHub.
- New runtime secret: `COMPOSIO_CONNECTED_ACCOUNT_ID` (a connection identifier, not a token).
  Read from the environment; never committed. `COMPOSIO_API_KEY` was already required by the gate.
- The fail-safe guarantees no stale-as-live and no 500 on a live failure.

## Files touched

- `sprintsight/connect/connector.py` — rewrite `fetch_issues`, add `_issues_from_response`,
  add `import os`.
- `sprintsight/web/crosstool_service.py` — extend `_crosstool_live_enabled()` /
  `_crosstool_config()` to require `COMPOSIO_CONNECTED_ACCOUNT_ID`.
- `tests/test_connect.py` — add `_issues_from_response` tests (+ a recorded new-SDK envelope).
- `tests/web/...crosstool...` — add the gate-requires-connection-id test.
- `docs/connectors/live-run.md` — update the live Jira command to the new env vars.
- `pyproject.toml` — pin `composio` to a compatible range (e.g. `composio>=0.16,<0.17`) so the
  rewritten API the code targets is the one that installs.

## Learning-queue flag

New concept for the learning log: "SDK version drift" (code written against one version of a
third-party SDK breaks when a newer, rewritten version installs; the fix is to target and pin the
current API). Pointer: this slice.
