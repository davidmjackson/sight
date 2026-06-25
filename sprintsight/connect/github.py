"""The GitHub side of the cross-tool watermelon (Goal B), read-only.

Mirrors the Jira connector seam: a tiny walled-off `fetch_github` (network) and a PURE
`index_activity` that groups GitHub facts (branches, PRs, commits) under each Jira key it
finds in a branch name, PR title, or commit message. The key match is the join to Jira.
"""

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# A Jira key like SSSB-4: uppercase project code, dash, number. Word-bounded so an
# embedded run like "xSSSB-4y" does not false-join to a ticket.
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


@dataclass(frozen=True)
class PR:
    number: int
    state: str
    merged: bool
    title: str
    url: str


@dataclass(frozen=True)
class Activity:
    """The GitHub facts for one Jira key. Small on purpose: just enough for the red rule."""

    key: str
    has_branch: bool
    prs: list[PR]
    commit_count: int
    last_commit_at: str | None


def _keys_in(text: str) -> set[str]:
    return set(KEY_RE.findall(text or ""))


def index_activity(items: list[dict[str, Any]]) -> dict[str, Activity]:
    """Group GitHub items by the Jira key(s) referenced in their text. Pure."""
    acc: dict[str, dict[str, Any]] = {}
    for it in items:
        kind = it.get("type")
        text = " ".join(str(it.get(f, "")) for f in ("name", "title", "message"))
        for key in _keys_in(text):
            bucket = acc.setdefault(
                key, {"has_branch": False, "prs": [], "commit_count": 0, "last_commit_at": None}
            )
            if kind == "branch":
                bucket["has_branch"] = True
            elif kind == "pr":
                bucket["prs"].append(
                    PR(
                        number=int(it.get("number", 0)),
                        state=str(it.get("state", "")),
                        merged=bool(it.get("merged", False)),
                        title=str(it.get("title", "")),
                        url=str(it.get("url", "")),
                    )
                )
            elif kind == "commit":
                bucket["commit_count"] += 1
                ts = it.get("committed_at")
                if ts and (bucket["last_commit_at"] is None or ts > bucket["last_commit_at"]):
                    bucket["last_commit_at"] = ts
    return {
        key: Activity(
            key=key,
            has_branch=b["has_branch"],
            prs=b["prs"],
            commit_count=b["commit_count"],
            last_commit_at=b["last_commit_at"],
        )
        for key, b in acc.items()
    }


class GitHubActivityConnector(Protocol):
    def fetch_activity(self) -> dict[str, Activity]: ...


class RecordedGitHubConnector:
    """Offline twin: indexes a recorded list of clean GitHub item dicts. No network."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    @classmethod
    def from_file(cls, path: str | Path) -> "RecordedGitHubConnector":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def fetch_activity(self) -> dict[str, Activity]:
        return index_activity(self._items)


def fetch_github(repo: str) -> list[dict[str, Any]]:
    """Network: read `repo`'s branches, PRs, and commits, returned as clean item dicts.

    The GitHub client is imported lazily so the module imports without it and so no test
    touches the network (tests inject a fake fetcher into GitHubConnector instead). The exact
    client call is confirmed at live-run time; this function is the single place it lives.
    Until a live run, use RecordedGitHubConnector.
    """
    from github import Github  # lazy: runtime-only dependency

    gh = Github(os.environ["GITHUB_TOKEN"])
    r = gh.get_repo(repo)
    items: list[dict[str, Any]] = []
    for b in r.get_branches():
        items.append({"type": "branch", "name": b.name})
    for pr in r.get_pulls(state="all"):
        items.append(
            {
                "type": "pr",
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "merged": pr.merged,
                "url": pr.html_url,
            }
        )
    for c in r.get_commits():
        items.append(
            {
                "type": "commit",
                "message": c.commit.message,
                "committed_at": c.commit.committer.date.isoformat(),
            }
        )
    return items


class GitHubConnector:
    """Live connector. `fetcher` is injectable so tests run without a network."""

    def __init__(
        self,
        repo: str,
        fetcher: Callable[[str], list[dict[str, Any]]] = fetch_github,
    ) -> None:
        self._repo = repo
        self._fetcher = fetcher

    def fetch_activity(self) -> dict[str, Activity]:
        return index_activity(self._fetcher(self._repo))
