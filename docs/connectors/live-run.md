# Running the connectors against live data

Plain-English summary: the two connectors (Jira read, GitHub read) are tested fully offline.
To run them against the real tools you install two SDKs and provide your own credentials. This
is the one piece that needs a human, because it needs secrets only you hold. Everything below is
read-only. Nothing writes to Jira or GitHub.

## One-time setup

Install the connector SDKs (declared as an optional extra). Install the app **editable**
(`-e`) so the command-line scripts and the web server run the live source, not a frozen
copy in site-packages:

    pip install -e '.[connectors,web]'

Gotcha learned the hard way: a plain `pip install '.[connectors]'` puts a snapshot of the
app in site-packages. The scripts then import that stale snapshot (old code) instead of your
working tree. The `-e` (editable) flag links site-packages back to the source so your edits
take effect. The test suite always uses the source, so this trap only bites the scripts and
the web server, not the tests.

## Live GitHub read (cross-tool watermelon, Goal B)

You need a read-only GitHub token in the environment. Create a fine-grained token with
read-only "Contents", "Pull requests", and "Metadata" on the demo repo, then:

    export GITHUB_TOKEN=<your-read-only-token>
    python scripts/run_cross_tool.py --repo davidmjackson/sprintsight-sandbox --project SSSB

This reads the real SSSB Jira board and the real sandbox repo and prints the cross-tool
watermelons, each citing both tools. Expected today: SSSB-1 (In Progress, no code) and SSSB-2
(Done, PR #1 open) flag; SSSB-3 (Done, PR merged) does not.

Real-shape note: GitHub's pull-request *list* endpoint reports `merged=false` even for merged
PRs, so `fetch_github` derives the merged flag from `merged_at`. This is calibrated in one place
(`sprintsight/connect/github.py`).

## Live Jira read (Goal A)

The Jira read goes through Composio, reusing the already-connected Jira account, so it needs a
Composio API key and a connected account id rather than a Jira token:

    export COMPOSIO_API_KEY=<your-composio-key>
    export COMPOSIO_CONNECTED_ACCOUNT_ID=<your-ca_... connection id>
    export COMPOSIO_USER_ID=<your-user-id from the Users page>
    python scripts/run_connector_demo.py --project SSSB

composio 0.16 needs all THREE: the account API key authenticates the app; the `ca_...`
connection id plus the owning User ID together identify which connected Jira account to read
(the SDK 400s with `ConnectedAccountEntityIdRequired` if the User ID is missing). The connector
also passes `dangerously_skip_version_check=True` because manual `tools.execute` refuses to run
without a pinned toolkit version and rejects "latest".

The connection id identifies which connected Jira account Composio reads; the connector reads it from `COMPOSIO_CONNECTED_ACCOUNT_ID` and never commits it.

Where to find the two values in the Composio dashboard:
- `COMPOSIO_API_KEY` is your account API key. If the API Keys page is empty you must CREATE one
  (it is shown once; copy it in full). It is a long string; a short value (around 15 characters)
  is a partial paste or the wrong id, and Composio rejects it with `401 Invalid API key`.
- `COMPOSIO_CONNECTED_ACCOUNT_ID` is the `ca_...` id of the connected account. Find it via Users
  -> click the user -> its connected account. (The `ac_...` id under Auth Configs is a different
  thing and will not work here.)
- `COMPOSIO_USER_ID` is the user/entity id on the Users page.

Same-terminal rule: `export` only sets a variable for the current terminal. Set both vars and
run the script in the **one** terminal window. If you open a new tab, the variables are gone
(check with `echo "key_len=${#COMPOSIO_API_KEY} id=${COMPOSIO_CONNECTED_ACCOUNT_ID:-MISSING}"`,
which prints lengths only, never the secret).

## Offline equivalents (no secrets, used in CI and demos)

These run the exact same connector logic against captured real data, no network:

    python scripts/run_cross_tool.py \
      --recorded data/captured/github_sandbox_live.json \
      --jira-recorded data/captured/jira_SSSB_live.json

## Status

The offline paths are exercised by the test suite and the captured-replay demos. The
`fetch_issues` Jira path targets the current Composio SDK (`Composio().tools.execute(...)`) and is
**LIVE-VERIFIED end to end (2026-06-26)**: a real read of project SSSB returned 6 tickets, ingested
and retrievable (top cited SSSB-1). Calibration result: the composio 0.16 response is a plain dict
`{"data": {"issues": [...]}, "error": ..., "successful": ...}` (NOT an object), so
`_issues_from_response` reads it dict-first; the inner issue shape matched `_to_clean` unchanged.
The GitHub `fetch_github` path via PyGithub is unchanged and still needs only a `GITHUB_TOKEN`.
