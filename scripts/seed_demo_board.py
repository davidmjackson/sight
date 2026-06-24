"""Seed a sandbox Jira board from our ground truth (Stage 7, Goal A).

`build_issue_specs()` is PURE (no Jira calls) and authored from the ground-truth scenario, so it
is fully tested offline. `main()` is the GATED create loop: it only runs when a Composio client is
available, and it is human-run by Claude via the Composio MCP on a clean-network day. The app
itself never runs this — seeding is one-time setup, not part of the read-only connector.

    .venv/bin/python scripts/seed_demo_board.py SSD       # creates issues in project SSD
"""

import sys
from typing import Any

# Authored from data/ground-truth/labels.yaml + the burndown corpus. One entry per ticket.
# Atlas (watermelon) carries the hidden cross-team dependency in a comment; Boreas is true-green.
SEED_PLAN: list[dict[str, Any]] = [
    {
        "team": "Atlas",
        "sprint": 15,
        "summary": "Wire auth token refresh",
        "story_points": 5,
        "status": "In Progress",
        "description": "Refresh tokens before expiry; blocked on upstream auth API.",
        "comments": ["heads up, Draco's auth API still isn't ready, this will bite us"],
    },
    {
        "team": "Atlas",
        "sprint": 15,
        "summary": "Checkout regression sweep",
        "story_points": 3,
        "status": "Done",
        "description": "Regression pass on checkout.",
        "comments": [],
    },
    {
        "team": "Atlas",
        "sprint": 15,
        "summary": "Carry-over: profile edit bug",
        "story_points": 5,
        "status": "To Do",
        "description": "Carried from sprint 14.",
        "comments": [],
    },
    {
        "team": "Boreas",
        "sprint": 15,
        "summary": "Dashboard spacing polish",
        "story_points": 2,
        "status": "Done",
        "description": "Tidy dashboard spacing.",
        "comments": [],
    },
    {
        "team": "Boreas",
        "sprint": 15,
        "summary": "Add export to CSV",
        "story_points": 3,
        "status": "Done",
        "description": "CSV export on reports.",
        "comments": [],
    },
    {
        "team": "Boreas",
        "sprint": 15,
        "summary": "Mitigate vendor latency risk",
        "story_points": 2,
        "status": "Done",
        "description": "Risk logged with owner and mitigation.",
        "comments": [],
    },
]


def build_issue_specs() -> list[dict[str, Any]]:
    """Expand SEED_PLAN into Jira-ready issue specs, adding the team label."""
    specs: list[dict[str, Any]] = []
    for row in SEED_PLAN:
        spec = dict(row)
        spec["labels"] = [f"team:{row['team'].lower()}", "sprintsight-demo-data"]
        specs.append(spec)
    return specs


def main(project_key: str) -> int:
    """GATED: create the issues in Jira via Composio. Human-run on a clean-network day."""
    from composio import ComposioToolSet  # lazy: runtime-only

    toolset = ComposioToolSet()
    created = 0
    for spec in build_issue_specs():
        toolset.execute_action(
            action="JIRA_CREATE_ISSUE",
            params={
                "project": project_key,
                "summary": spec["summary"],
                "description": spec["description"],
                "labels": spec["labels"],
                "issuetype": "Task",
            },
        )
        created += 1
    print(f"OK — created {created} issues in {project_key}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: seed_demo_board.py <PROJECT_KEY>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
