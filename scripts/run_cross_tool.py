"""Goal B demo: cross-tool watermelon from Jira tickets + GitHub activity.

Offline by default via captured replay. Live needs a Composio key (Jira) and GITHUB_TOKEN.

Usage:
  python scripts/run_cross_tool.py --recorded data/captured/github_sample_live.json \
      --jira-recorded data/captured/jira_demo_live.json
  python scripts/run_cross_tool.py --repo owner/name --project SSSB   # live

The two captured fixtures share SSSB-* keys so the offline demo shows discrimination:
SSSB-1 (In Progress, no work) and SSSB-2 (Done, open PR) flag; SSSB-3 (Done, merged PR) does not.
"""

import argparse
import json
from datetime import UTC, datetime

from sprintsight.connect.connector import JiraConnector, RecordedConnector
from sprintsight.connect.github import GitHubConnector, RecordedGitHubConnector
from sprintsight.connect.jira_tickets import tickets_from_artifacts
from sprintsight.crosstool import run_cross_tool


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

    tickets = tickets_from_artifacts(jira.fetch())
    as_of = datetime.now(UTC).isoformat()
    verdicts = run_cross_tool(tickets, gh.fetch_activity(), as_of=as_of)

    watermelons = [v for v in verdicts if v.is_watermelon]
    stalled = [v for v in verdicts if v.actual_status == "amber"]
    print(
        f"{len(verdicts)} tickets checked, {len(watermelons)} watermelon(s), "
        f"{len(stalled)} stalled:"
    )
    for v in watermelons:
        print(json.dumps(
            {"watermelon": v.team, "evidence": v.evidence, "why": v.explanation}, indent=2))
    for v in stalled:
        print(json.dumps(
            {"stalled": v.team, "evidence": v.evidence, "why": v.explanation}, indent=2))


if __name__ == "__main__":
    main()
