# Running the connectors against live data

Plain-English summary: the two connectors (Jira read, GitHub read) are tested fully offline.
To run them against the real tools you install two SDKs and provide your own credentials. This
is the one piece that needs a human, because it needs secrets only you hold. Everything below is
read-only. Nothing writes to Jira or GitHub.

## One-time setup

Install the connector SDKs (declared as an optional extra):

    pip install '.[connectors]'

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
Composio API key rather than a Jira token:

    export COMPOSIO_API_KEY=<your-composio-key>
    python scripts/run_connector_demo.py --project SSSB

## Offline equivalents (no secrets, used in CI and demos)

These run the exact same connector logic against captured real data, no network:

    python scripts/run_cross_tool.py \
      --recorded data/captured/github_sandbox_live.json \
      --jira-recorded data/captured/jira_SSSB_live.json

## Status

The offline paths are exercised by the test suite and the captured-replay demos. The live SDK
fetch paths (`fetch_github` via PyGithub, `fetch_issues` via the Composio SDK) are walled off and
have not yet been run end to end from the app; the live proof to date was produced by seeding and
reading both tools via their MCP integrations, then replaying the captured real data through the
connector logic. Running the SDK paths above is the remaining step and only needs the credentials.
