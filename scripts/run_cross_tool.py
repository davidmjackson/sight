"""Goal B demo: cross-tool watermelon from Jira tickets + GitHub activity.

Offline by default via captured replay. Live needs a Composio key (Jira) and GITHUB_TOKEN.

Usage:
  python scripts/run_cross_tool.py --recorded data/captured/github_sample_live.json \
      --jira-recorded tests/fixtures/jira_sample.json
  python scripts/run_cross_tool.py --repo owner/name --project SSSB   # live
"""

import argparse
import json

from sprintsight.connect.connector import JiraConnector, RecordedConnector
from sprintsight.connect.github import GitHubConnector, RecordedGitHubConnector
from sprintsight.crosstool import run_cross_tool


def _tickets_from_artifacts(artifacts: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for art in artifacts.values():
        key = art.meta.get("source_ref", art.artifact_id)
        # status rides in the body's meta line: "**Status:** In Progress · ..."
        status = ""
        for line in art.body.splitlines():
            if "Status:" in line:
                status = line.split("Status:", 1)[1].split("·")[0].strip().strip("*").strip()
                break
        out[key] = {"key": key, "status": status, "team": art.team}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recorded", help="captured GitHub items JSON")
    ap.add_argument("--jira-recorded", help="captured Jira issues JSON")
    ap.add_argument("--repo", help="owner/name for a live GitHub read")
    ap.add_argument("--project", help="Jira project key for a live read")
    args = ap.parse_args()

    gh = (
        RecordedGitHubConnector.from_file(args.recorded)
        if args.recorded
        else GitHubConnector(args.repo)
    )
    jira = (
        RecordedConnector.from_file(args.jira_recorded)
        if args.jira_recorded
        else JiraConnector(args.project)
    )

    tickets = _tickets_from_artifacts(jira.fetch())
    verdicts = run_cross_tool(tickets, gh.fetch_activity())

    flagged = [v for v in verdicts if v.is_watermelon]
    print(f"{len(verdicts)} tickets checked, {len(flagged)} cross-tool watermelon(s):")
    for v in flagged:
        print(
            json.dumps(
                {"team": v.team, "evidence": v.evidence, "why": v.explanation}, indent=2
            )
        )


if __name__ == "__main__":
    main()
