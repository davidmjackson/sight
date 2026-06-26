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
    export COMPOSIO_CONNECTED_ACCOUNT_ID=<your-ac_... connection id>
    python scripts/run_connector_demo.py --project SSSB

The connection id identifies which connected Jira account Composio reads; the connector reads it from `COMPOSIO_CONNECTED_ACCOUNT_ID` and never commits it.

Where to find the two values in the Composio dashboard:
- `COMPOSIO_API_KEY` is your account API key, under Settings / API Keys. It is a long string.
  A short value (around 15 characters) is a partial paste, and Composio rejects it with
  `401 Invalid API key`.
- `COMPOSIO_CONNECTED_ACCOUNT_ID` is under Connected accounts / Connections, on the Jira row.
  It looks like `ca_...`.

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
`fetch_issues` Jira path now targets the current Composio SDK (`Composio().tools.execute(...)`,
ported 2026-06-26). A first live attempt confirmed the port is correct: with the editable
install in place the script reached a real authenticated Composio call and the SDK accepted the
request shape, failing only at credential validation (`401 Invalid API key`) because a partial
key was pasted. So the remaining step is purely supplying a valid `COMPOSIO_API_KEY` plus the
`ca_...` connection id; once a real read returns, confirm the response arrives as `{"issues":
[...]}` under `resp.data` and that the inner issue shape still matches `_to_clean` (adjust only
`_issues_from_response` / `_to_clean` and their fixtures if it differs). The GitHub `fetch_github`
path via PyGithub is unchanged and still needs only a `GITHUB_TOKEN`.
