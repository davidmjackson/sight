# Jira Connector (Goal A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one read-only Jira connector that turns live Jira tickets into the existing `Artifact` shape and prove it end to end with a script (Goal A — "prove the pipe").

**Architecture:** A new `sprintsight/connect/` module with three split pieces: `fetch_issues()` (the only network call, hides Jira's custom-field mess behind a stable simplified dict), `normalize()` (a pure clean-dict -> Artifact translator, the hard-tested unit), and `JiraConnector.fetch()` (ties them together behind a `Connector` protocol, with an offline `RecordedConnector` twin). Everything downstream (ingest, retrieval) is reused unchanged.

**Tech Stack:** Python 3.11+, dataclasses, pytest, Composio Python SDK (lazy import, runtime only), the existing `ingest_corpus` pipeline and `InMemoryRetriever`.

## Global Constraints

- Reuse the existing `Artifact` dataclass from `sprintsight/evals/fixtures.py`. Do NOT define a new one.
- `source_type` must be `"jira"` (a valid DB enum value; the set is `{jira, confluence, slack, raid, other}`).
- Connector is READ-ONLY. The app never writes to Jira. (The seed script writes; it is one-time human-run setup.)
- All tests run fully offline. No test may make a network call. The Composio SDK is imported lazily inside `fetch_issues` only, so the module imports without it installed.
- No web UI changes in this slice.
- `ruff` must stay clean. Run `.venv/bin/ruff check .` before each commit.
- Frequent commits: one per task, after its tests pass.
- The stable simplified issue dict (the contract between `fetch_issues` and `normalize`) has exactly these keys: `key` (str), `summary` (str), `status` (str), `team` (str), `sprint` (int), `story_points` (int|None), `assignee` (str|None), `reporter` (str|None), `updated` (str|None), `description` (str), `comments` (list[str]).

---

### Task 1: The pure translator — `normalize()` + body renderer

**Files:**
- Create: `sprintsight/connect/__init__.py`
- Create: `sprintsight/connect/normalize.py`
- Test: `tests/test_connect.py`

**Interfaces:**
- Consumes: `Artifact` from `sprintsight.evals.fixtures`.
- Produces: `normalize(issue: dict) -> Artifact`; `render_body(issue: dict) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_connect.py
"""Stage 7 connector (Goal A): clean-dict -> Artifact translation, offline."""

from sprintsight.connect.normalize import normalize, render_body

SAMPLE_ISSUE = {
    "key": "SSD-12",
    "summary": "Wire auth token refresh",
    "status": "In Progress",
    "team": "Atlas",
    "sprint": 15,
    "story_points": 5,
    "assignee": "Dev One",
    "reporter": "PM Atlas",
    "updated": "2026-05-20T10:00:00Z",
    "description": "Refresh tokens before expiry.",
    "comments": ["heads up, Draco's auth API still isn't ready, this will bite us"],
}


def test_normalize_maps_core_fields():
    art = normalize(SAMPLE_ISSUE)
    assert art.artifact_id == "jira-SSD-12"
    assert art.source_type == "jira"
    assert art.team == "Atlas"
    assert art.sprint == 15
    assert art.meta["source_ref"] == "SSD-12"
    assert art.meta["title"] == "Wire auth token refresh"
    assert art.meta["author"] == "Dev One"            # assignee preferred over reporter
    assert art.meta["source_timestamp"] == "2026-05-20T10:00:00Z"


def test_render_body_carries_key_facts():
    body = render_body(SAMPLE_ISSUE)
    assert "SSD-12" in body
    assert "In Progress" in body
    assert "5" in body                                 # story points
    assert "Refresh tokens before expiry." in body
    assert "Draco's auth API still isn't ready" in body  # comment text is citable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_connect.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.connect'`

- [ ] **Step 3: Write minimal implementation**

```python
# sprintsight/connect/__init__.py
"""Stage 7 connectors (Goal A): turn live delivery-tool data into corpus Artifacts.

The Jira-specific, network-touching code lives in `connector.fetch_issues` and emits a stable
simplified issue dict. `normalize` maps that clean dict to the existing `Artifact` shape, so the
rest of the app (ingest, retrieval) is reused unchanged.
"""
```

```python
# sprintsight/connect/normalize.py
"""Pure translation: a stable simplified Jira issue dict -> the corpus `Artifact` shape.

No network here. The simplified dict (produced by `connector.fetch_issues`) hides Jira's raw
custom-field shape, so this stays trivially testable and deterministic.
"""

from typing import Any

from sprintsight.evals.fixtures import Artifact


def render_body(issue: dict[str, Any]) -> str:
    """Markdown render of one issue: the human-readable, citable text that gets embedded."""
    meta_line = (
        f"**Key:** {issue['key']} · **Status:** {issue.get('status', '')} · "
        f"**Sprint:** {issue.get('sprint', '')} · **Points:** {issue.get('story_points', '')} · "
        f"**Assignee:** {issue.get('assignee') or ''}"
    )
    parts = [f"# {issue.get('summary', issue['key'])}", "", meta_line]
    description = (issue.get("description") or "").strip()
    if description:
        parts += ["", description]
    comments = issue.get("comments") or []
    if comments:
        parts += ["", "## Comments"] + [f"- {c}" for c in comments]
    return "\n".join(parts)


def normalize(issue: dict[str, Any]) -> Artifact:
    """Map one simplified Jira issue dict to an Artifact. Pure; same input -> same output."""
    key = issue["key"]
    return Artifact(
        artifact_id=f"jira-{key}",
        source_type="jira",
        team=issue.get("team", ""),
        sprint=int(issue.get("sprint", 0)),
        meta={
            "source_ref": key,
            "title": issue.get("summary"),
            "author": issue.get("assignee") or issue.get("reporter"),
            "source_timestamp": issue.get("updated"),
        },
        body=render_body(issue),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_connect.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check sprintsight/connect tests/test_connect.py
git add sprintsight/connect/__init__.py sprintsight/connect/normalize.py tests/test_connect.py
git commit -m "feat(stage7): pure Jira issue -> Artifact normalizer [SS-5]"
```

---

### Task 2: The seam — `Connector` protocol + `RecordedConnector` + offline fixture

**Files:**
- Create: `sprintsight/connect/connector.py`
- Create: `tests/fixtures/jira_sample.json`
- Test: `tests/test_connect.py` (append)

**Interfaces:**
- Consumes: `normalize` from `sprintsight.connect.normalize`; `Artifact`.
- Produces: `Connector` protocol with `fetch() -> dict[str, Artifact]`; `RecordedConnector(issues: list[dict])` and `RecordedConnector.from_file(path) -> RecordedConnector`.

- [ ] **Step 1: Create the offline fixture**

Create `tests/fixtures/jira_sample.json` (a list of simplified issue dicts; this is the deterministic test anchor, refreshed from the live board later):

```json
[
  {
    "key": "SSD-12",
    "summary": "Wire auth token refresh",
    "status": "In Progress",
    "team": "Atlas",
    "sprint": 15,
    "story_points": 5,
    "assignee": "Dev One",
    "reporter": "PM Atlas",
    "updated": "2026-05-20T10:00:00Z",
    "description": "Refresh tokens before expiry.",
    "comments": ["heads up, Draco's auth API still isn't ready, this will bite us"]
  },
  {
    "key": "SSD-13",
    "summary": "Checkout regression sweep",
    "status": "Done",
    "team": "Atlas",
    "sprint": 15,
    "story_points": 3,
    "assignee": "Dev Two",
    "reporter": "PM Atlas",
    "updated": "2026-05-19T16:00:00Z",
    "description": "Regression pass on checkout flow.",
    "comments": []
  },
  {
    "key": "SSD-40",
    "summary": "Boreas dashboard polish",
    "status": "Done",
    "team": "Boreas",
    "sprint": 15,
    "story_points": 2,
    "assignee": "Dev Three",
    "reporter": "PM Boreas",
    "updated": "2026-05-19T12:00:00Z",
    "description": "Tidy dashboard spacing.",
    "comments": []
  }
]
```

- [ ] **Step 2: Write the failing test**

```python
# append to tests/test_connect.py
from pathlib import Path

from sprintsight.connect.connector import RecordedConnector

FIXTURE = Path(__file__).parent / "fixtures" / "jira_sample.json"


def test_recorded_connector_returns_artifacts_keyed_by_id():
    conn = RecordedConnector.from_file(FIXTURE)
    artifacts = conn.fetch()
    assert set(artifacts) == {"jira-SSD-12", "jira-SSD-13", "jira-SSD-40"}
    assert all(a.source_type == "jira" for a in artifacts.values())
    assert artifacts["jira-SSD-12"].team == "Atlas"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_connect.py::test_recorded_connector_returns_artifacts_keyed_by_id -v`
Expected: FAIL with `ImportError: cannot import name 'RecordedConnector'`

- [ ] **Step 4: Write minimal implementation**

```python
# sprintsight/connect/connector.py
"""The connector seam: a `Connector` returns corpus Artifacts. `RecordedConnector` reads a saved
sample (offline twin); `JiraConnector` (Task 4) pulls from the live board. Same seam pattern as
the embedder / store / auth / writer seams.
"""

import json
from pathlib import Path
from typing import Protocol

from sprintsight.connect.normalize import normalize
from sprintsight.evals.fixtures import Artifact


class Connector(Protocol):
    def fetch(self) -> dict[str, Artifact]: ...


def _to_artifacts(issues: list[dict]) -> dict[str, Artifact]:
    artifacts = [normalize(i) for i in issues]
    return {a.artifact_id: a for a in artifacts}


class RecordedConnector:
    """Offline twin: normalizes a recorded list of simplified issue dicts. No network."""

    def __init__(self, issues: list[dict]) -> None:
        self._issues = issues

    @classmethod
    def from_file(cls, path: str | Path) -> "RecordedConnector":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def fetch(self) -> dict[str, Artifact]:
        return _to_artifacts(self._issues)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_connect.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff check sprintsight/connect tests/test_connect.py
git add sprintsight/connect/connector.py tests/fixtures/jira_sample.json tests/test_connect.py
git commit -m "feat(stage7): Connector seam + RecordedConnector + offline fixture [SS-5]"
```

---

### Task 3: Prove the seam integrates with the unchanged pipeline (offline end-to-end)

**Files:**
- Test: `tests/test_connect.py` (append)

**Interfaces:**
- Consumes: `RecordedConnector`; `ingest_corpus` from `sprintsight.ingest`; `InMemoryStore`; `HashingEmbedder`; `InMemoryRetriever`.
- Produces: nothing new — this task is the integration gate that proves connector output flows through ingest and retrieval with no downstream changes.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_connect.py
from sprintsight.ingest import ingest_corpus
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.ingest.store import InMemoryStore
from sprintsight.retrieval.retriever import InMemoryRetriever


def test_connector_output_ingests_and_is_retrievable():
    artifacts = RecordedConnector.from_file(FIXTURE).fetch()

    store = InMemoryStore()
    emb = HashingEmbedder()
    report = ingest_corpus(store, emb, artifacts=artifacts)
    assert report.artifacts_total == 3
    assert report.ingested == 3
    assert report.chunks_written >= 3

    # Idempotent: a second run over the same store adds nothing.
    again = ingest_corpus(store, emb, artifacts=artifacts)
    assert again.ingested == 0
    assert again.skipped == 3

    # Retrievable with jira provenance.
    retriever = InMemoryRetriever(emb, artifacts=artifacts)
    results = retriever.search("auth api dependency not ready", team="Atlas")
    assert results, "expected at least one retrieved chunk"
    assert all(r.source_type == "jira" for r in results)
    assert all(r.source_ref.startswith("SSD-") for r in results)
```

- [ ] **Step 2: Run test to verify it passes (no new code needed — this proves reuse)**

Run: `.venv/bin/pytest tests/test_connect.py -v`
Expected: PASS (4 passed). If it fails, the connector output shape does not match what the pipeline expects — fix the connector/normalizer, not the pipeline.

- [ ] **Step 3: Commit**

```bash
git add tests/test_connect.py
git commit -m "test(stage7): connector output flows through ingest + retrieval unchanged [SS-5]"
```

---

### Task 4: `JiraConnector` + `fetch_issues` (live path, injectable fetcher)

**Files:**
- Modify: `sprintsight/connect/connector.py`
- Test: `tests/test_connect.py` (append)

**Interfaces:**
- Consumes: `_to_artifacts`; `normalize`.
- Produces: `fetch_issues(project_key: str) -> list[dict]` (network, lazy Composio import); `JiraConnector(project_key: str, fetcher: Callable[[str], list[dict]] = fetch_issues)` with `fetch() -> dict[str, Artifact]`.

- [ ] **Step 1: Write the failing test (inject a fake fetcher — no network)**

```python
# append to tests/test_connect.py
from sprintsight.connect.connector import JiraConnector


def test_jira_connector_uses_injected_fetcher():
    fake_issues = [
        {"key": "SSD-99", "summary": "x", "status": "To Do", "team": "Echo",
         "sprint": 15, "story_points": 1, "assignee": None, "reporter": "PM",
         "updated": "2026-05-21T09:00:00Z", "description": "", "comments": []}
    ]
    conn = JiraConnector("SSD", fetcher=lambda project_key: fake_issues)
    artifacts = conn.fetch()
    assert list(artifacts) == ["jira-SSD-99"]
    assert artifacts["jira-SSD-99"].team == "Echo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_connect.py::test_jira_connector_uses_injected_fetcher -v`
Expected: FAIL with `ImportError: cannot import name 'JiraConnector'`

- [ ] **Step 3: Add the implementation to `connector.py`**

Append to `sprintsight/connect/connector.py`:

```python
from typing import Any, Callable


def fetch_issues(project_key: str) -> list[dict[str, Any]]:
    """Network: pull issues for `project_key` from Jira via the Composio SDK, reusing the
    already-connected Jira account, and return stable simplified issue dicts.

    The Composio SDK is imported lazily so the module imports without it installed and so no
    test touches the network (tests inject a fake fetcher into JiraConnector instead).

    The exact Composio action slug and Jira custom-field IDs (sprint, story points) are confirmed
    at live-run time against the connected account; `_to_clean` is the single place that mapping
    lives. Until a live run, use RecordedConnector.
    """
    from composio import ComposioToolSet  # lazy: runtime-only dependency

    toolset = ComposioToolSet()
    raw = toolset.execute_action(
        action="JIRA_SEARCH_ISSUES",
        params={"jql": f"project = {project_key} ORDER BY updated DESC", "maxResults": 100},
    )
    return [_to_clean(issue) for issue in raw.get("data", {}).get("issues", [])]


def _to_clean(raw: dict[str, Any]) -> dict[str, Any]:
    """Map one raw Jira API issue to the stable simplified dict normalize() expects.

    Single home for Jira's custom-field mess. Field IDs below are the Jira Cloud defaults for a
    team-managed project; confirm against the connected account on the first live run.
    """
    f = raw.get("fields", {})
    team = ""
    for label in f.get("labels", []) or []:
        if label.startswith("team:"):
            team = label.split(":", 1)[1].capitalize()
            break
    sprint = 0
    sprint_field = f.get("customfield_10020") or []
    if sprint_field:
        name = (sprint_field[-1] or {}).get("name", "")
        digits = "".join(ch for ch in name if ch.isdigit())
        sprint = int(digits) if digits else 0
    comments = [c.get("body", "") for c in (f.get("comment", {}) or {}).get("comments", [])]
    return {
        "key": raw.get("key", ""),
        "summary": f.get("summary", ""),
        "status": (f.get("status", {}) or {}).get("name", ""),
        "team": team,
        "sprint": sprint,
        "story_points": f.get("customfield_10016"),
        "assignee": (f.get("assignee") or {}).get("displayName"),
        "reporter": (f.get("reporter") or {}).get("displayName"),
        "updated": f.get("updated"),
        "description": f.get("description") or "",
        "comments": comments,
    }


class JiraConnector:
    """Live connector. `fetcher` is injectable so tests run without a network."""

    def __init__(
        self,
        project_key: str,
        fetcher: Callable[[str], list[dict[str, Any]]] = fetch_issues,
    ) -> None:
        self._project_key = project_key
        self._fetcher = fetcher

    def fetch(self) -> dict[str, Artifact]:
        return _to_artifacts(self._fetcher(self._project_key))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_connect.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check sprintsight/connect
git add sprintsight/connect/connector.py tests/test_connect.py
git commit -m "feat(stage7): JiraConnector + Composio fetch_issues (injectable, lazy import) [SS-5]"
```

---

### Task 5: Seed-board builder — `build_issue_specs()` from ground truth (+ gated create loop)

**Files:**
- Create: `scripts/seed_demo_board.py`
- Test: `tests/test_seed_board.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (independent builder).
- Produces: `SEED_PLAN` (dict authored from ground truth); `build_issue_specs() -> list[dict]` where each spec has keys `summary, team, sprint, story_points, status, description, comments, labels`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_board.py
"""Stage 7: the seed-board builder is pure and deterministic (no Jira calls)."""

from scripts.seed_demo_board import build_issue_specs


def test_build_issue_specs_covers_teams_and_sprints():
    specs = build_issue_specs()
    assert len(specs) >= 6
    teams = {s["team"] for s in specs}
    assert {"Atlas", "Boreas"} <= teams
    assert {15} <= {s["sprint"] for s in specs}


def test_every_spec_has_team_label_and_points():
    for s in build_issue_specs():
        assert any(lbl == f"team:{s['team'].lower()}" for lbl in s["labels"])
        assert isinstance(s["story_points"], int)


def test_atlas_dependency_signal_is_seeded():
    specs = build_issue_specs()
    atlas_text = " ".join(
        " ".join(s["comments"]) + " " + s["description"]
        for s in specs if s["team"] == "Atlas"
    )
    assert "Draco" in atlas_text  # the cross-team dependency phrase is present to grade against
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_seed_board.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.seed_demo_board'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/seed_demo_board.py
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
    {"team": "Atlas", "sprint": 15, "summary": "Wire auth token refresh",
     "story_points": 5, "status": "In Progress",
     "description": "Refresh tokens before expiry; blocked on upstream auth API.",
     "comments": ["heads up, Draco's auth API still isn't ready, this will bite us"]},
    {"team": "Atlas", "sprint": 15, "summary": "Checkout regression sweep",
     "story_points": 3, "status": "Done", "description": "Regression pass on checkout.",
     "comments": []},
    {"team": "Atlas", "sprint": 15, "summary": "Carry-over: profile edit bug",
     "story_points": 5, "status": "To Do", "description": "Carried from sprint 14.",
     "comments": []},
    {"team": "Boreas", "sprint": 15, "summary": "Dashboard spacing polish",
     "story_points": 2, "status": "Done", "description": "Tidy dashboard spacing.",
     "comments": []},
    {"team": "Boreas", "sprint": 15, "summary": "Add export to CSV",
     "story_points": 3, "status": "Done", "description": "CSV export on reports.",
     "comments": []},
    {"team": "Boreas", "sprint": 15, "summary": "Mitigate vendor latency risk",
     "story_points": 2, "status": "Done",
     "description": "Risk logged with owner and mitigation.", "comments": []},
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_seed_board.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check scripts/seed_demo_board.py tests/test_seed_board.py
git add scripts/seed_demo_board.py tests/test_seed_board.py
git commit -m "feat(stage7): seed-board builder from ground truth (pure) + gated Jira create [SS-5]"
```

---

### Task 6: The A1 proof — `run_connector_demo.py`

**Files:**
- Create: `scripts/run_connector_demo.py`
- Test: `tests/test_connector_demo.py`

**Interfaces:**
- Consumes: `RecordedConnector`, `JiraConnector`; `ingest_corpus`; `HashingEmbedder`; `InMemoryStore`; `InMemoryRetriever`.
- Produces: `run_demo(connector, query: str) -> dict` returning `{"artifacts": int, "ingested": int, "results": int, "top_source_ref": str | None}`; `main(argv) -> int`.

- [ ] **Step 1: Write the failing test (recorded mode, offline)**

```python
# tests/test_connector_demo.py
"""Stage 7 A1 proof: the demo runs end to end offline via RecordedConnector."""

from pathlib import Path

from scripts.run_connector_demo import run_demo
from sprintsight.connect.connector import RecordedConnector

FIXTURE = Path(__file__).parent / "fixtures" / "jira_sample.json"


def test_demo_pulls_ingests_and_retrieves():
    conn = RecordedConnector.from_file(FIXTURE)
    out = run_demo(conn, query="auth api dependency not ready")
    assert out["artifacts"] == 3
    assert out["ingested"] == 3
    assert out["results"] >= 1
    assert out["top_source_ref"].startswith("SSD-")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_connector_demo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.run_connector_demo'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/run_connector_demo.py
"""A1 proof (Stage 7, Goal A): pull live Jira tickets, normalize, ingest, retrieve — and print
real tickets as cited evidence. No web UI.

    # offline, against the recorded sample (default):
    .venv/bin/python scripts/run_connector_demo.py

    # live, against a real board (clean-network day, Composio key set):
    .venv/bin/python scripts/run_connector_demo.py --project SSD

This is the "done" artifact for the slice: it proves the connector pipe end to end.
"""

import argparse
import json
import sys
from pathlib import Path

from sprintsight.connect.connector import Connector, JiraConnector, RecordedConnector
from sprintsight.ingest import ingest_corpus
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.ingest.store import InMemoryStore
from sprintsight.retrieval.retriever import InMemoryRetriever

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "jira_sample.json"
DEFAULT_QUERY = "auth api dependency not ready"


def run_demo(connector: Connector, query: str = DEFAULT_QUERY) -> dict:
    """Fetch -> ingest -> retrieve. Returns a small machine-readable summary."""
    artifacts = connector.fetch()

    emb = HashingEmbedder()
    store = InMemoryStore()
    report = ingest_corpus(store, emb, artifacts=artifacts)

    retriever = InMemoryRetriever(emb, artifacts=artifacts)
    results = retriever.search(query, k=5)

    return {
        "artifacts": len(artifacts),
        "ingested": report.ingested,
        "results": len(results),
        "top_source_ref": results[0].source_ref if results else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jira connector A1 proof")
    parser.add_argument("--project", help="live Jira project key (omit for offline recorded mode)")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    args = parser.parse_args(argv)

    connector: Connector = (
        JiraConnector(args.project)
        if args.project
        else RecordedConnector.from_file(DEFAULT_FIXTURE)
    )
    out = run_demo(connector, query=args.query)
    print("RESULT " + json.dumps(out))
    if out["results"] < 1:
        print("FAIL: connector returned no retrievable evidence")
        return 1
    print(f"OK — {out['artifacts']} real tickets ingested; top cited ticket {out['top_source_ref']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_connector_demo.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Run the demo for real (offline mode) and eyeball the output**

Run: `.venv/bin/python scripts/run_connector_demo.py`
Expected: a `RESULT {...}` line then `OK — 3 real tickets ingested; top cited ticket SSD-...`

- [ ] **Step 6: Full suite + lint, then commit**

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
git add scripts/run_connector_demo.py tests/test_connector_demo.py
git commit -m "feat(stage7): A1 connector demo — pull, ingest, retrieve, cite [SS-5]"
```

---

### Task 7: Docs + handover update

**Files:**
- Modify: `HANDOVER.md`
- Modify: `docs/superpowers/specs/2026-06-24-jira-connector-design.md` (mark BUILT)

- [ ] **Step 1: Update HANDOVER.md** "Where we are" to record the connector slice is built (connector + seam + offline tests + A1 demo green), and add a Learning-queue line: `Jira connector (Goal A) | first real external-tool read, normalized into the existing Artifact shape behind a Connector seam | sprintsight/connect/ | 2026-06-24`.

- [ ] **Step 2: Note the two remaining live setup steps** (David creates the sandbox project + gives its key; confirm Composio API key) and that running `seed_demo_board.py` + a live `run_connector_demo.py --project <KEY>` is the clean-network-day follow-up.

- [ ] **Step 3: Commit**

```bash
git add HANDOVER.md docs/superpowers/specs/2026-06-24-jira-connector-design.md
git commit -m "docs(stage7): handover + spec status for Jira connector slice [SS-5]"
```

---

## Self-Review

**Spec coverage:** connector module (Tasks 1,2,4) ✓; pure normalizer hard-tested (Task 1) ✓; Connector seam + offline twin (Task 2) ✓; reuse of unchanged ingest/retrieval proven (Task 3) ✓; live Composio fetch walled off + injectable (Task 4) ✓; seed board from ground truth (Task 5) ✓; A1 script proof, no UI (Task 6) ✓; eval-first via recorded fixture, CI offline (Tasks 1-3,6) ✓; read-only + new-secret flag + deferred items (docs, Task 7) ✓. No web UI changes anywhere ✓.

**Placeholder scan:** every code step contains full code; no TBD/TODO. The only deliberately deferred concretes are the Composio action slug and Jira custom-field IDs, which are isolated in `fetch_issues`/`_to_clean` and explicitly confirmed at live-run time (they cannot be known on a no-network day, and no offline test depends on them).

**Type consistency:** `normalize(issue: dict) -> Artifact`, `Connector.fetch() -> dict[str, Artifact]`, `fetch_issues(project_key) -> list[dict]`, `JiraConnector(project_key, fetcher)`, `build_issue_specs() -> list[dict]`, `run_demo(connector, query) -> dict` are used consistently across tasks. The simplified-issue-dict keys in Global Constraints match the fixture, `_to_clean` output, and what `normalize`/`render_body` read.
