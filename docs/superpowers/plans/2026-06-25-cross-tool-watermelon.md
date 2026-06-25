# Cross-Tool Watermelon (Goal B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only GitHub connector and a pure cross-tool reconciler that flags a per-ticket "status versus activity" watermelon (Jira says progressing, GitHub shows no work / unmerged PR), proven by an offline eval and reusing the existing `Verdict` contract.

**Architecture:** A new `GitHubConnector` mirrors the existing `JiraConnector` seam: a tiny walled-off network fetch plus a pure `index_activity` that groups GitHub facts under each Jira key. A new pure `reconcile(inputs) -> Verdict` compares the Jira status against that activity. A new 5-case eval runs the reconciler through the existing `run_suite` harness with the same dual gate (classification + evidence). The existing burndown detector and the RAG pipeline are untouched.

**Tech Stack:** Python 3.12, dataclasses, `pytest`, `ruff`. Live GitHub read deferred to a hand-run demo script (lazy-imported client); CI stays fully offline.

## Global Constraints

- Second tool = **GitHub, read-only**. Never write to GitHub or Jira. Recommend-only.
- Detection unit = **per-ticket**. No team rollup in this slice.
- Red rule v1 = exactly two conditions: (a) claims progress (In Progress / In Review / Done) but NO branch/PR/commit references the key; (b) Done but linked PR open / unmerged.
- Jira-to-GitHub join = the **ticket key** (`[A-Z][A-Z0-9]+-\d+`) in a branch name, PR title, or commit message.
- **Reuse the existing `Verdict`** dataclass from `sprintsight/evals/watermelon.py`. Do not define a new verdict shape.
- v1 colours are **green and red only**. Amber is reserved for the deferred "stalled" signal.
- `sprintsight/detector.py` and the existing CI gates must **not** be edited.
- Eval-first: the cross-tool eval must exist and be RED (null reconciler) before `reconcile` logic is written.
- No network in any test. The live fetch is exercised only by the demo script.
- No em dashes in any prose written for David.

---

### Task 1: GitHub activity model + pure indexer

**Files:**
- Create: `sprintsight/connect/github.py`
- Test: `tests/test_github_connector.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `@dataclass(frozen=True) PR` with fields `number: int, state: str, merged: bool, title: str, url: str`
  - `@dataclass(frozen=True) Activity` with fields `key: str, has_branch: bool, prs: list[PR], commit_count: int, last_commit_at: str | None`
  - `index_activity(items: list[dict[str, Any]]) -> dict[str, Activity]` — pure; groups GitHub items by Jira key.
  - Input item shape (the clean dicts the network layer will emit): `{"type": "branch"|"pr"|"commit", "name": str, "title": str, "message": str, "number": int, "state": str, "merged": bool, "url": str, "committed_at": str}` (only the fields relevant to each `type` need be present).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_github_connector.py
"""Stage 7 cross-tool connector (Goal B): GitHub activity indexing, offline."""

from sprintsight.connect.github import Activity, PR, index_activity

ITEMS = [
    {"type": "branch", "name": "feature/SSSB-4-auth-refresh"},
    {"type": "pr", "number": 12, "title": "SSSB-4 auth refresh", "state": "open",
     "merged": False, "url": "https://gh/pr/12"},
    {"type": "commit", "message": "SSSB-4 wip on refresh", "committed_at": "2026-06-20T10:00:00Z"},
    {"type": "commit", "message": "SSSB-4 more", "committed_at": "2026-06-21T10:00:00Z"},
    {"type": "pr", "number": 30, "title": "SSSB-9 ship dashboard", "state": "closed",
     "merged": True, "url": "https://gh/pr/30"},
]


def test_index_groups_facts_by_key():
    idx = index_activity(ITEMS)
    assert set(idx) == {"SSSB-4", "SSSB-9"}

    a4 = idx["SSSB-4"]
    assert a4.has_branch is True
    assert a4.commit_count == 2
    assert a4.last_commit_at == "2026-06-21T10:00:00Z"  # newest wins
    assert [p.number for p in a4.prs] == [12]
    assert a4.prs[0].merged is False and a4.prs[0].state == "open"

    a9 = idx["SSSB-9"]
    assert a9.has_branch is False
    assert a9.commit_count == 0
    assert a9.prs[0].merged is True


def test_index_ignores_text_without_a_key():
    assert index_activity([{"type": "commit", "message": "no ticket here"}]) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_github_connector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.connect.github'`

- [ ] **Step 3: Write minimal implementation**

```python
# sprintsight/connect/github.py
"""The GitHub side of the cross-tool watermelon (Goal B), read-only.

Mirrors the Jira connector seam: a tiny walled-off `fetch_github` (network) and a PURE
`index_activity` that groups GitHub facts (branches, PRs, commits) under each Jira key it
finds in a branch name, PR title, or commit message. The key match is the join to Jira.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# A Jira key like SSSB-4: uppercase project code, dash, number.
KEY_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_github_connector.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add sprintsight/connect/github.py tests/test_github_connector.py
git commit -m "feat(stage7): GitHub activity model + pure key indexer (Goal B) [SS-5]"
```

---

### Task 2: GitHub connector seam (recorded twin + injectable live fetch)

**Files:**
- Modify: `sprintsight/connect/github.py` (append)
- Test: `tests/test_github_connector.py` (append)

**Interfaces:**
- Consumes: `Activity`, `index_activity` from Task 1.
- Produces:
  - `class GitHubActivityConnector(Protocol)` with `fetch_activity(self) -> dict[str, Activity]`
  - `RecordedGitHubConnector(items)` and `RecordedGitHubConnector.from_file(path)` — offline twin.
  - `fetch_github(repo: str) -> list[dict[str, Any]]` — walled network fetch (lazy import).
  - `class GitHubConnector(repo, fetcher=fetch_github)` with `fetch_activity() -> dict[str, Activity]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_github_connector.py
from pathlib import Path

from sprintsight.connect.github import (
    GitHubConnector,
    RecordedGitHubConnector,
)

FIXTURE = Path(__file__).parent / "fixtures" / "github_sample.json"


def test_recorded_connector_indexes_from_file(tmp_path):
    sample = tmp_path / "gh.json"
    sample.write_text(
        '[{"type": "pr", "number": 7, "title": "SSSB-2 wire login", '
        '"state": "closed", "merged": true, "url": "u"}]',
        encoding="utf-8",
    )
    idx = RecordedGitHubConnector.from_file(sample).fetch_activity()
    assert set(idx) == {"SSSB-2"}
    assert idx["SSSB-2"].prs[0].merged is True


def test_github_connector_uses_injected_fetcher():
    fake_items = [{"type": "branch", "name": "feat/SSSB-5-thing"}]
    conn = GitHubConnector("owner/repo", fetcher=lambda repo: fake_items)
    idx = conn.fetch_activity()
    assert set(idx) == {"SSSB-5"}
    assert idx["SSSB-5"].has_branch is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_github_connector.py -k "recorded_connector_indexes or injected_fetcher" -v`
Expected: FAIL with `ImportError: cannot import name 'GitHubConnector'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to sprintsight/connect/github.py


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

    import os

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_github_connector.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add sprintsight/connect/github.py tests/test_github_connector.py
git commit -m "feat(stage7): GitHub connector seam (recorded twin + injectable live fetch) [SS-5]"
```

---

### Task 3: Cross-tool eval, RED with a null reconciler (eval-first gate)

**Files:**
- Create: `sprintsight/evals/crosstool_eval.py`
- Create: `docs/evals/cross-tool-watermelon-eval.md`
- Test: `tests/test_cross_tool_eval.py`

**Interfaces:**
- Consumes: `Activity`, `PR` from Task 1; `Verdict`, `run_suite`, `Case`, `Assertion` from existing modules.
- Produces:
  - `CASES: list[dict]` — the 5 fixture records (`ticket`, `activity`, `expected_*`, `required_evidence`).
  - `build_cases() -> list[Case]` — dual-gated (classification + evidence).
  - `run_cross_tool_eval(reconciler) -> SuiteReport`.
  - `null_reconciler(inputs) -> Verdict` — abstains, so the suite is RED.
  - Reconciler input contract: `inputs = {"ticket": {"key": str, "status": str, "team": str}, "activity": Activity | None}`.

- [ ] **Step 1: Write the eval spec doc**

```markdown
# docs/evals/cross-tool-watermelon-eval.md

# Cross-tool watermelon eval (Goal B, SS-5)

Per-ticket "status versus activity" watermelon: Jira says a ticket is progressing, GitHub shows
no work for it, or it was called Done with an unmerged PR. Reuses the SS-1.4 `Verdict` contract
and the deterministic harness, dual-gated exactly like the team watermelon eval:

- classification: `is_watermelon` AND `actual_status` must equal the ground truth.
- evidence: every required token must appear in the verdict's `evidence` list.

A case passes only when BOTH gates pass. Subject under test: `reconcile(inputs) -> Verdict`,
`inputs = {"ticket": {key,status,team}, "activity": Activity|None}`. Until `reconcile` exists,
`null_reconciler` abstains so the suite is RED (the eval-first signal).

## Cases

| Case | Jira status | GitHub activity        | is_watermelon | actual | Required evidence |
|------|-------------|------------------------|---------------|--------|-------------------|
| 1    | In Progress | none                   | true          | red    | jira-SSSB-1, github:no-ref:SSSB-1 |
| 2    | Done        | PR #12 open, unmerged  | true          | red    | jira-SSSB-2, github:PR#12:open-unmerged |
| 3    | In Progress | PR #5 open + 3 commits | false         | green  | (none) |
| 4    | Done        | PR #8 merged           | false         | green  | (none) |
| 5    | To Do       | none                   | false         | green  | (none) |

Cases 4 and 5 are the false-positive guards: a merged PR is healthy, a backlog ticket is not lying.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_cross_tool_eval.py
"""Goal B cross-tool watermelon eval is RED until reconcile() exists (eval-first)."""

from sprintsight.evals.crosstool_eval import null_reconciler, run_cross_tool_eval


def test_red_without_a_reconciler():
    report = run_cross_tool_eval(null_reconciler)
    assert report.pass_rate == 0.0
    # The two true watermelons must be among the failures while abstaining.
    assert {"case1", "case2"} <= set(report.summary()["failures"])
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_cross_tool_eval.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.evals.crosstool_eval'`

- [ ] **Step 4: Write the eval module (cases, gates, null reconciler)**

```python
# sprintsight/evals/crosstool_eval.py
"""Cross-tool watermelon eval (Goal B, SS-5).

Implements docs/evals/cross-tool-watermelon-eval.md on the generic harness. Five per-ticket
cases pairing a Jira status with GitHub Activity, dual-gated (classification + evidence) like
the team watermelon eval. Subject under test: a reconciler `reconcile(inputs) -> Verdict`.
Until SS-5's reconcile exists, `null_reconciler` abstains, so the suite is RED by design.
"""

from collections.abc import Callable
from typing import Any

from sprintsight.connect.github import PR, Activity
from sprintsight.evals.harness import Assertion, Case, SuiteReport, run_suite
from sprintsight.evals.watermelon import Verdict

Reconciler = Callable[[dict[str, Any]], Verdict]
Check = Callable[[Verdict], Assertion]


def _act(key: str, **kw: Any) -> Activity:
    return Activity(
        key=key,
        has_branch=kw.get("has_branch", False),
        prs=kw.get("prs", []),
        commit_count=kw.get("commit_count", 0),
        last_commit_at=kw.get("last_commit_at"),
    )


CASES: list[dict[str, Any]] = [
    {
        "name": "case1",
        "ticket": {"key": "SSSB-1", "status": "In Progress", "team": "Atlas"},
        "activity": None,
        "is_watermelon": True,
        "actual": "red",
        "required_evidence": {"jira-SSSB-1", "github:no-ref:SSSB-1"},
    },
    {
        "name": "case2",
        "ticket": {"key": "SSSB-2", "status": "Done", "team": "Atlas"},
        "activity": _act(
            "SSSB-2",
            prs=[PR(number=12, state="open", merged=False, title="SSSB-2", url="u")],
        ),
        "is_watermelon": True,
        "actual": "red",
        "required_evidence": {"jira-SSSB-2", "github:PR#12:open-unmerged"},
    },
    {
        "name": "case3",
        "ticket": {"key": "SSSB-3", "status": "In Progress", "team": "Boreas"},
        "activity": _act(
            "SSSB-3",
            prs=[PR(number=5, state="open", merged=False, title="SSSB-3", url="u")],
            commit_count=3,
        ),
        "is_watermelon": False,
        "actual": "green",
        "required_evidence": set(),
    },
    {
        "name": "case4",
        "ticket": {"key": "SSSB-4", "status": "Done", "team": "Boreas"},
        "activity": _act(
            "SSSB-4",
            prs=[PR(number=8, state="closed", merged=True, title="SSSB-4", url="u")],
        ),
        "is_watermelon": False,
        "actual": "green",
        "required_evidence": set(),
    },
    {
        "name": "case5",
        "ticket": {"key": "SSSB-5", "status": "To Do", "team": "Cygnus"},
        "activity": None,
        "is_watermelon": False,
        "actual": "green",
        "required_evidence": set(),
    },
]


def _classification(expected_watermelon: bool, expected_actual: str) -> Check:
    def check(v: Verdict) -> Assertion:
        ok = v.is_watermelon == expected_watermelon and v.actual_status == expected_actual
        return Assertion(
            "classification",
            ok,
            f"is_watermelon={v.is_watermelon} (want {expected_watermelon}), "
            f"actual={v.actual_status} (want {expected_actual})",
        )

    return check


def _evidence(required: set[str]) -> Check:
    def check(v: Verdict) -> Assertion:
        missing = required - set(v.evidence)
        return Assertion(
            "evidence",
            not missing,
            f"missing={sorted(missing)}" if missing else "all required evidence cited",
        )

    return check


def build_cases() -> list[Case]:
    cases: list[Case] = []
    for rec in CASES:
        cases.append(
            Case(
                name=rec["name"],
                inputs={"ticket": rec["ticket"], "activity": rec["activity"]},
                assertions=[
                    _classification(rec["is_watermelon"], rec["actual"]),
                    _evidence(rec["required_evidence"]),
                ],
            )
        )
    return cases


def null_reconciler(inputs: dict[str, Any]) -> Verdict:
    """Placeholder until reconcile() exists. Abstains, so the suite is RED."""
    return Verdict(
        team=inputs["ticket"].get("team", ""),
        reported_status="unknown",
        actual_status="unknown",
        is_watermelon=False,
        evidence=[],
        explanation="no reconciler implemented yet",
    )


def run_cross_tool_eval(reconciler: Reconciler | None = None) -> SuiteReport:
    return run_suite(build_cases(), reconciler or null_reconciler)
```

- [ ] **Step 5: Run test to verify it passes (suite is RED, as asserted)**

Run: `pytest tests/test_cross_tool_eval.py -v`
Expected: PASS (the test asserts `pass_rate == 0.0`)

- [ ] **Step 6: Commit**

```bash
git add sprintsight/evals/crosstool_eval.py docs/evals/cross-tool-watermelon-eval.md tests/test_cross_tool_eval.py
git commit -m "test(stage7): cross-tool watermelon eval RED with null reconciler (eval-first) [SS-5]"
```

---

### Task 4: Implement `reconcile` and turn the eval GREEN

**Files:**
- Create: `sprintsight/crosstool.py`
- Modify: `tests/test_cross_tool_eval.py` (append a green-suite test)
- Test: `tests/test_crosstool_reconcile.py`

**Interfaces:**
- Consumes: `Activity` (Task 1); `Verdict` (existing); `CASES`, `run_cross_tool_eval` (Task 3).
- Produces: `reconcile(inputs: dict[str, Any]) -> Verdict`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_crosstool_reconcile.py
"""Goal B reconciler: per-ticket status-vs-activity watermelon logic."""

from sprintsight.connect.github import PR, Activity
from sprintsight.crosstool import reconcile


def _v(status, activity, key="SSSB-1", team="Atlas"):
    return reconcile({"ticket": {"key": key, "status": status, "team": team}, "activity": activity})


def test_in_progress_no_work_is_watermelon():
    v = _v("In Progress", None)
    assert v.is_watermelon is True
    assert v.actual_status == "red"
    assert "jira-SSSB-1" in v.evidence
    assert "github:no-ref:SSSB-1" in v.evidence


def test_done_with_open_pr_is_watermelon():
    act = Activity("SSSB-1", False, [PR(12, "open", False, "t", "u")], 0, None)
    v = _v("Done", act)
    assert v.is_watermelon is True
    assert v.actual_status == "red"
    assert "github:PR#12:open-unmerged" in v.evidence


def test_in_progress_with_work_is_clean():
    act = Activity("SSSB-1", True, [PR(5, "open", False, "t", "u")], 3, None)
    v = _v("In Progress", act)
    assert v.is_watermelon is False
    assert v.actual_status == "green"


def test_done_with_merged_pr_is_clean():
    act = Activity("SSSB-1", False, [PR(8, "closed", True, "t", "u")], 0, None)
    v = _v("Done", act)
    assert v.is_watermelon is False
    assert v.actual_status == "green"


def test_backlog_ticket_is_never_a_watermelon():
    v = _v("To Do", None)
    assert v.is_watermelon is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crosstool_reconcile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.crosstool'`

- [ ] **Step 3: Write the implementation**

```python
# sprintsight/crosstool.py
"""Cross-tool watermelon reconciler (Goal B, SS-5).

Pure, recommend-only. Compares one Jira ticket's reported status against its GitHub Activity
and emits the existing SS-1.4 `Verdict`. The red rule (v1): a ticket claiming progress with no
linked work, or a Done ticket whose PR is still open/unmerged, is "actually red" while it reads
as healthy in Jira, i.e. a watermelon. Colours are green/red only; amber is reserved for the
deferred staleness signal. Never writes to GitHub or Jira.
"""

from typing import Any

from sprintsight.connect.github import Activity
from sprintsight.evals.watermelon import Verdict

_PROGRESS = {"in progress", "in review", "done"}


def _has_work(activity: Activity | None) -> bool:
    return activity is not None and (
        activity.has_branch or bool(activity.prs) or activity.commit_count > 0
    )


def reconcile(inputs: dict[str, Any]) -> Verdict:
    """`inputs = {"ticket": {key,status,team}, "activity": Activity | None}` -> Verdict."""
    ticket = inputs["ticket"]
    activity: Activity | None = inputs.get("activity")
    key = ticket["key"]
    team = ticket.get("team", "")
    status = str(ticket.get("status", "")).strip().lower()

    reported = "green" if status in _PROGRESS else "n/a"

    # actual_status and the GitHub-side evidence token.
    open_prs = [p for p in (activity.prs if activity else []) if not p.merged]
    if status == "done":
        merged = any(p.merged for p in activity.prs) if activity else False
        if merged:
            actual, gh = "green", f"github:active:{key}"
        elif open_prs:
            actual, gh = "red", f"github:PR#{open_prs[0].number}:open-unmerged"
        else:
            actual, gh = "red", f"github:no-ref:{key}"
    elif status in {"in progress", "in review"}:
        if _has_work(activity):
            actual, gh = "green", f"github:active:{key}"
        else:
            actual, gh = "red", f"github:no-ref:{key}"
    else:  # To Do / Backlog: not claiming progress, never a watermelon.
        actual, gh = "green", f"github:n/a:{key}"

    is_watermelon = reported == "green" and actual == "red"
    evidence = [f"jira-{key}", gh] if is_watermelon else [f"jira-{key}"]

    verb = "looks healthier than its code activity" if is_watermelon else "matches its code activity"
    explanation = f"{key} reported {reported}; computed actual {actual} ({verb})."

    return Verdict(
        team=team,
        reported_status=reported,
        actual_status=actual,
        is_watermelon=is_watermelon,
        evidence=evidence,
        signals=[gh],
        explanation=explanation,
    )
```

- [ ] **Step 4: Run the reconciler unit tests**

Run: `pytest tests/test_crosstool_reconcile.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Add the green-suite test**

```python
# append to tests/test_cross_tool_eval.py
from sprintsight.crosstool import reconcile


def test_green_with_the_real_reconciler():
    report = run_cross_tool_eval(reconcile)
    assert report.pass_rate == 1.0
    assert report.dimension_rates()["classification"] == (5, 5)
    assert report.dimension_rates()["evidence"] == (5, 5)
```

- [ ] **Step 6: Run the full cross-tool eval suite**

Run: `pytest tests/test_cross_tool_eval.py -v`
Expected: PASS (RED test and GREEN test both pass)

- [ ] **Step 7: Commit**

```bash
git add sprintsight/crosstool.py tests/test_crosstool_reconcile.py tests/test_cross_tool_eval.py
git commit -m "feat(stage7): cross-tool reconciler turns Goal B eval green (5/5) [SS-5]"
```

---

### Task 5: Orchestrator + offline demo script

**Files:**
- Modify: `sprintsight/crosstool.py` (append `run_cross_tool`)
- Create: `scripts/run_cross_tool.py`
- Create: `data/captured/github_sample_live.json`
- Test: `tests/test_crosstool_reconcile.py` (append `run_cross_tool` test)

**Interfaces:**
- Consumes: `reconcile` (Task 4); `JiraConnector`/`RecordedConnector` (existing); `GitHubConnector`/`RecordedGitHubConnector` (Task 2).
- Produces: `run_cross_tool(tickets: dict[str, dict], activity: dict[str, Activity]) -> list[Verdict]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_crosstool_reconcile.py
from sprintsight.crosstool import run_cross_tool


def test_run_cross_tool_flags_only_watermelons():
    tickets = {
        "SSSB-1": {"key": "SSSB-1", "status": "In Progress", "team": "Atlas"},
        "SSSB-2": {"key": "SSSB-2", "status": "Done", "team": "Atlas"},
    }
    act = {"SSSB-2": Activity("SSSB-2", True, [PR(8, "closed", True, "t", "u")], 1, None)}
    verdicts = run_cross_tool(tickets, act)
    flagged = [v for v in verdicts if v.is_watermelon]
    assert [v.team for v in verdicts] == ["Atlas", "Atlas"]  # one verdict per ticket
    assert len(flagged) == 1  # SSSB-1 (no work); SSSB-2 has a merged PR
    assert "jira-SSSB-1" in flagged[0].evidence
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_crosstool_reconcile.py::test_run_cross_tool_flags_only_watermelons -v`
Expected: FAIL with `ImportError: cannot import name 'run_cross_tool'`

- [ ] **Step 3: Implement the orchestrator**

```python
# append to sprintsight/crosstool.py


def run_cross_tool(
    tickets: dict[str, dict[str, Any]],
    activity: dict[str, Activity],
) -> list[Verdict]:
    """Reconcile every Jira ticket against its GitHub activity (matched by key)."""
    return [
        reconcile({"ticket": ticket, "activity": activity.get(key)})
        for key, ticket in tickets.items()
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_crosstool_reconcile.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Create the captured replay sample**

```json
[
  {"type": "branch", "name": "feature/SSSB-2-auth-refresh"},
  {"type": "pr", "number": 12, "title": "SSSB-2 auth refresh", "state": "open", "merged": false, "url": "https://gh/pr/12"},
  {"type": "pr", "number": 8, "title": "SSSB-3 dashboard", "state": "closed", "merged": true, "url": "https://gh/pr/8"},
  {"type": "commit", "message": "SSSB-3 ship dashboard", "committed_at": "2026-06-21T10:00:00Z"}
]
```

- [ ] **Step 6: Write the demo script**

```python
# scripts/run_cross_tool.py
"""Goal B demo: cross-tool watermelon from Jira tickets + GitHub activity.

Offline by default via captured replay. Live needs a Composio key (Jira) and GITHUB_TOKEN.

Usage:
  python scripts/run_cross_tool.py --recorded data/captured/github_sample_live.json
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
        # status rides in the body's meta line: "**Status:** In Progress"
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
        print(json.dumps({"team": v.team, "evidence": v.evidence, "why": v.explanation}, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Smoke-run the demo offline**

Run: `python scripts/run_cross_tool.py --recorded data/captured/github_sample_live.json --jira-recorded tests/fixtures/jira_sample.json`
Expected: prints a tickets-checked line and zero or more watermelon JSON blocks, no traceback.

- [ ] **Step 8: Commit**

```bash
git add sprintsight/crosstool.py scripts/run_cross_tool.py data/captured/github_sample_live.json tests/test_crosstool_reconcile.py
git commit -m "feat(stage7): cross-tool orchestrator + offline demo script [SS-5]"
```

---

### Task 6: Full gate, docs, and handover

**Files:**
- Modify: `HANDOVER.md`
- Modify: `docs/superpowers/specs/2026-06-25-cross-tool-watermelon-design.md` (status line)

- [ ] **Step 1: Run the whole suite + linter**

Run: `pytest -q && ruff check .`
Expected: all tests pass (193 prior + the new tests), ruff clean. Confirm the existing watermelon eval still 4/4 and report eval 4/4 (unchanged).

- [ ] **Step 2: Update the spec status line**

Change the spec's `Status:` line to `BUILT (offline). Live-verify pending.` with today's date and the branch name.

- [ ] **Step 3: Update HANDOVER.md**

Add a "Where we are" note: Goal B built offline (GitHub connector + reconciler + 5/5 cross-tool eval), live-verify against a seeded demo repo pending. Append one line to the `Learning queue` section: `cross-tool reconciliation | first watermelon that needs two live tools joined on the ticket key | sprintsight/crosstool.py | 2026-06-25`.

- [ ] **Step 4: Commit**

```bash
git add HANDOVER.md docs/superpowers/specs/2026-06-25-cross-tool-watermelon-design.md
git commit -m "docs(stage7): handover + spec status for Goal B offline build [SS-5]"
```

---

## Live-verify (run by hand, after the offline build is reviewed and merged)

Not a coding task. Steps, one at a time, on a clean-network day:
1. Decide and create a throwaway demo repo (e.g. `sssb-demo`); seed branches/PRs that reference the real SSSB keys so at least one ticket is a true watermelon (Done + open PR) and one is honest.
2. Capture the live GitHub read to `data/captured/github_<repo>_live.json`.
3. Run `scripts/run_cross_tool.py --repo <owner/repo> --project SSSB` and confirm it flags the planted watermelon citing both tools.
4. Update the spec status to LIVE-VERIFIED and add a memory.

## Self-review notes

- Spec coverage: GitHub connector (Tasks 1-2), reconciler + red rule (Task 4), eval-first 5 cases (Task 3), orchestrator + demo + captured replay (Task 5), live-verify plan (final section), security/read-only (Global Constraints + demo script uses read-only token). All spec sections map to a task.
- `Verdict` reused unchanged; `detector.py` untouched; no new verdict shape.
- Type consistency: `Activity`/`PR` fields and `reconcile`/`run_cross_tool` signatures are identical across Tasks 1, 3, 4, 5.
