# Stalled-PR Signal (amber) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an amber "stalled PR" tier to the cross-tool reconciler: an In Progress / In Review ticket whose open PR has not been touched in 7 days is flagged amber (a warning, never a watermelon), proven by new offline eval cases.

**Architecture:** One optional field (`updated_at`) is added to the `PR` shape and read by `fetch_github`. `reconcile` gains a middle branch that, for progress-claiming tickets with an open PR, computes the freshest activity timestamp (newest open PR `updated_at` or `last_commit_at`) against an injected `as_of` and a configurable threshold; older than the threshold becomes `actual = "amber"`. `is_watermelon` stays red-only. The watermelon (red) and green rules are untouched.

**Tech Stack:** Python 3.11+, dataclasses, `datetime` (stdlib), `pytest`, `ruff`.

## Global Constraints

- Amber is a warning, NOT a watermelon. `is_watermelon` stays `reported == "green" and actual == "red"`. Amber tickets get `is_watermelon = False`.
- Threshold defaults to **7 days**, read from inputs as `stale_after_days` so it is tunable without a code change.
- Freshness source = the newest open PR's `updated_at`, with `Activity.last_commit_at` as a secondary signal. Stale only if the freshest of the two is older than the threshold.
- Amber applies ONLY to `in progress` / `in review` tickets that have an open PR. The Done and no-work rules are untouched.
- Pure + injected: the reference "now" is `inputs["as_of"]`, never `datetime.now()`. When `as_of` is absent the staleness check is skipped, so the existing 5 cross-tool eval cases keep passing unchanged.
- Eval-first: stalled (amber) and fresh (green) eval cases land with the logic; boundary is age `>= 7` days = stalled, age `< 7` = green.
- Read-only. No new external call, no new secret, no writes.
- Reuse the existing `Verdict`. Do not touch `sprintsight/detector.py` or the existing CI gates.
- No em dashes in prose written for David.

---

### Task 1: Add `PR.updated_at` and read it in the GitHub layer

**Files:**
- Modify: `sprintsight/connect/github.py`
- Test: `tests/test_github_connector.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `PR` gains `updated_at: str | None = None`; `index_activity` maps `updated_at` from each PR item dict; `fetch_github` emits `updated_at` as an ISO string.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_github_connector.py
def test_index_carries_pr_updated_at():
    items = [{"type": "pr", "number": 9, "title": "SSSB-8 wip", "state": "open",
              "merged": False, "url": "u", "updated_at": "2026-06-15T00:00:00Z"}]
    idx = index_activity(items)
    assert idx["SSSB-8"].prs[0].updated_at == "2026-06-15T00:00:00Z"


def test_pr_updated_at_defaults_to_none():
    items = [{"type": "pr", "number": 9, "title": "SSSB-8", "state": "open",
              "merged": False, "url": "u"}]
    idx = index_activity(items)
    assert idx["SSSB-8"].prs[0].updated_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_github_connector.py -k updated_at -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'updated_at'` (or AttributeError on `.updated_at`).

- [ ] **Step 3: Add the field to `PR`**

In `sprintsight/connect/github.py`, change the `PR` dataclass:

```python
@dataclass(frozen=True)
class PR:
    number: int
    state: str
    merged: bool
    title: str
    url: str
    updated_at: str | None = None
```

- [ ] **Step 4: Map it in `index_activity`**

In the `elif kind == "pr":` block of `index_activity`, add `updated_at` to the `PR(...)` construction:

```python
            elif kind == "pr":
                bucket["prs"].append(
                    PR(
                        number=int(it.get("number", 0)),
                        state=str(it.get("state", "")),
                        merged=bool(it.get("merged", False)),
                        title=str(it.get("title", "")),
                        url=str(it.get("url", "")),
                        updated_at=it.get("updated_at"),
                    )
                )
```

- [ ] **Step 5: Emit it in `fetch_github`**

In `fetch_github`, in the `for pr in r.get_pulls(...)` loop, add `updated_at` to the appended dict:

```python
                "merged": pr.merged_at is not None,
                "url": pr.html_url,
                "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_github_connector.py -v`
Expected: PASS (all GitHub connector tests).

- [ ] **Step 7: Commit**

```bash
git add sprintsight/connect/github.py tests/test_github_connector.py
git commit -m "feat(stage7): carry PR.updated_at through the GitHub connector [SS-5]"
```

---

### Task 2: Add the amber/stalled branch to `reconcile`

**Files:**
- Modify: `sprintsight/crosstool.py`
- Test: `tests/test_crosstool_reconcile.py` (append)

**Interfaces:**
- Consumes: `Activity`, `PR` (Task 1); `Verdict` (existing).
- Produces: `reconcile(inputs)` now reads `inputs["as_of"]` (str | None) and `inputs.get("stale_after_days", 7)`, and can return `actual_status == "amber"` with evidence token `github:PR#<n>:stalled-<age>d`. New module-level helper `_stalled(activity, as_of, threshold_days) -> tuple[int, int] | None` returning `(pr_number, age_days)` or `None`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_crosstool_reconcile.py
AS_OF = "2026-06-25T00:00:00+00:00"


def _vt(status, activity, as_of=None, key="SSSB-1", team="Atlas"):
    return reconcile({
        "ticket": {"key": key, "status": status, "team": team},
        "activity": activity,
        "as_of": as_of,
    })


def test_in_progress_parked_pr_is_amber_not_watermelon():
    act = Activity("SSSB-1", False, [PR(20, "open", False, "t", "u", "2026-06-15T00:00:00Z")], 0, None)
    v = _vt("In Progress", act, AS_OF)
    assert v.actual_status == "amber"
    assert v.is_watermelon is False
    assert "github:PR#20:stalled-10d" in v.evidence
    assert "jira-SSSB-1" in v.evidence


def test_in_progress_fresh_pr_is_green():
    act = Activity("SSSB-1", False, [PR(21, "open", False, "t", "u", "2026-06-24T00:00:00Z")], 0, None)
    v = _vt("In Progress", act, AS_OF)
    assert v.actual_status == "green"
    assert v.is_watermelon is False


def test_stalled_boundary_is_inclusive_at_threshold():
    # exactly 7 days old -> stalled; 6 days -> green
    at7 = Activity("SSSB-1", False, [PR(1, "open", False, "t", "u", "2026-06-18T00:00:00Z")], 0, None)
    at6 = Activity("SSSB-1", False, [PR(1, "open", False, "t", "u", "2026-06-19T00:00:00Z")], 0, None)
    assert _vt("In Progress", at7, AS_OF).actual_status == "amber"
    assert _vt("In Progress", at6, AS_OF).actual_status == "green"


def test_no_as_of_skips_staleness_backcompat():
    # Without as_of, an old PR must behave exactly as before (green for has-work).
    act = Activity("SSSB-1", False, [PR(20, "open", False, "t", "u", "2026-01-01T00:00:00Z")], 0, None)
    v = _vt("In Progress", act, None)
    assert v.actual_status == "green"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crosstool_reconcile.py -k "stalled or amber or fresh or backcompat" -v`
Expected: FAIL (amber never returned; `actual_status` is `green`, assertions on `amber`/token fail).

- [ ] **Step 3: Add imports and the `_stalled` helper**

At the top of `sprintsight/crosstool.py`, add to the imports:

```python
from datetime import datetime, timezone
```

Add this helper above `reconcile`:

```python
def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _stalled(
    activity: Activity | None, as_of: str | None, threshold_days: int
) -> tuple[int, int] | None:
    """If the newest open PR (and any commits) have been quiet >= threshold_days as of
    `as_of`, return (pr_number, age_days); else None. Pure; None as_of skips the check."""
    now = _parse_ts(as_of)
    if activity is None or now is None:
        return None
    open_prs = [p for p in activity.prs if not p.merged]
    if not open_prs:
        return None
    floor = datetime.min.replace(tzinfo=timezone.utc)
    newest_pr = max(open_prs, key=lambda p: _parse_ts(p.updated_at) or floor)
    stamps = [
        t for t in (_parse_ts(newest_pr.updated_at), _parse_ts(activity.last_commit_at))
        if t is not None
    ]
    if not stamps:
        return None
    age_days = (now - max(stamps)).days
    if age_days >= threshold_days:
        return newest_pr.number, age_days
    return None
```

- [ ] **Step 4: Wire the amber branch into `reconcile`**

In `reconcile`, read the new inputs just after `status` is computed:

```python
    as_of = inputs.get("as_of")
    stale_after_days = int(inputs.get("stale_after_days", 7))
```

Replace the existing `elif status in {"in progress", "in review"}:` block with:

```python
    elif status in {"in progress", "in review"}:
        if not _has_work(activity):
            actual, gh = "red", f"github:no-ref:{key}"
        else:
            stalled = _stalled(activity, as_of, stale_after_days)
            if stalled is not None:
                pr_number, age_days = stalled
                actual, gh = "amber", f"github:PR#{pr_number}:stalled-{age_days}d"
            else:
                actual, gh = "green", f"github:active:{key}"
```

The amber evidence must be cited even though amber is not a watermelon. Change the evidence line from `evidence = [f"jira-{key}", gh] if is_watermelon else [f"jira-{key}"]` to:

```python
    cite_github = is_watermelon or actual == "amber"
    evidence = [f"jira-{key}", gh] if cite_github else [f"jira-{key}"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_crosstool_reconcile.py -v`
Expected: PASS (the new stalled tests plus all existing reconciler tests).

- [ ] **Step 6: Commit**

```bash
git add sprintsight/crosstool.py tests/test_crosstool_reconcile.py
git commit -m "feat(stage7): amber stalled-PR tier in the cross-tool reconciler [SS-5]"
```

---

### Task 3: Add stalled eval cases (amber) and thread `as_of`

**Files:**
- Modify: `sprintsight/evals/crosstool_eval.py`
- Modify: `docs/evals/cross-tool-watermelon-eval.md`
- Test: `tests/test_cross_tool_eval.py` (the existing green-suite test must still pass; no new test needed because the suite asserts full pass + dimension counts)

**Interfaces:**
- Consumes: `reconcile` (Task 2); `PR`, `Activity` (Task 1).
- Produces: `CASES` gains two records with an `as_of` key; `build_cases` threads `as_of` into inputs when present.

- [ ] **Step 1: Add the two cases to `CASES`**

In `sprintsight/evals/crosstool_eval.py`, add a module constant near the top (after the imports):

```python
AS_OF = "2026-06-25T00:00:00+00:00"
```

Append these two records to the `CASES` list (after case5):

```python
    {
        "name": "case6",
        "ticket": {"key": "SSSB-7", "status": "In Progress", "team": "Atlas"},
        "activity": _act(
            "SSSB-7",
            prs=[PR(number=20, state="open", merged=False, title="SSSB-7",
                    url="u", updated_at="2026-06-15T00:00:00Z")],
        ),
        "as_of": AS_OF,
        "is_watermelon": False,
        "actual": "amber",
        "required_evidence": {"jira-SSSB-7", "github:PR#20:stalled-10d"},
    },
    {
        "name": "case7",
        "ticket": {"key": "SSSB-8", "status": "In Progress", "team": "Boreas"},
        "activity": _act(
            "SSSB-8",
            prs=[PR(number=21, state="open", merged=False, title="SSSB-8",
                    url="u", updated_at="2026-06-24T00:00:00Z")],
        ),
        "as_of": AS_OF,
        "is_watermelon": False,
        "actual": "green",
        "required_evidence": set(),
    },
```

- [ ] **Step 2: Thread `as_of` through `build_cases`**

In `build_cases`, change the `inputs=` construction so an `as_of` is passed when the record has one:

```python
    for rec in CASES:
        inputs = {"ticket": rec["ticket"], "activity": rec["activity"]}
        if "as_of" in rec:
            inputs["as_of"] = rec["as_of"]
        cases.append(
            Case(
                name=rec["name"],
                inputs=inputs,
                assertions=[
                    _classification(rec["is_watermelon"], rec["actual"]),
                    _evidence(rec["required_evidence"]),
                ],
            )
        )
```

- [ ] **Step 3: Update the green-suite expectation**

In `tests/test_cross_tool_eval.py`, the `test_green_with_the_real_reconciler` test asserts dimension counts of `(5, 5)`. Update both to `(7, 7)`:

```python
def test_green_with_the_real_reconciler():
    report = run_cross_tool_eval(reconcile)
    assert report.pass_rate == 1.0
    assert report.dimension_rates()["classification"] == (7, 7)
    assert report.dimension_rates()["evidence"] == (7, 7)
```

- [ ] **Step 4: Run the eval suite**

Run: `pytest tests/test_cross_tool_eval.py -v`
Expected: PASS (RED null-reconciler test unchanged; green test now 7/7).

- [ ] **Step 5: Document the cases in the eval spec**

Append this section to `docs/evals/cross-tool-watermelon-eval.md`:

```markdown
## Stalled (amber)

A ticket claiming progress with an open PR that has gone quiet (no PR/commit activity for
`stale_after_days`, default 7, measured against an injected `as_of`) is flagged **amber /
stalled** - a warning, not a watermelon (`is_watermelon` stays False). Boundary: age >= 7 days
is stalled, age < 7 is green. When `as_of` is absent the check is skipped (back-compat).

| Case | Jira status | GitHub activity                        | actual | Required evidence |
|------|-------------|----------------------------------------|--------|-------------------|
| 6    | In Progress | open PR #20, updated 10 days ago       | amber  | jira-SSSB-7, github:PR#20:stalled-10d |
| 7    | In Progress | open PR #21, updated 1 day ago         | green  | (none) |
```

- [ ] **Step 6: Commit**

```bash
git add sprintsight/evals/crosstool_eval.py docs/evals/cross-tool-watermelon-eval.md tests/test_cross_tool_eval.py
git commit -m "test(stage7): stalled (amber) eval cases for the cross-tool reconciler [SS-5]"
```

---

### Task 4: Thread `as_of` through `run_cross_tool` and surface stalled in the demo

**Files:**
- Modify: `sprintsight/crosstool.py`
- Modify: `scripts/run_cross_tool.py`
- Modify: `data/captured/github_sandbox_live.json`
- Test: `tests/test_crosstool_reconcile.py` (append)

**Interfaces:**
- Consumes: `reconcile` (Task 2).
- Produces: `run_cross_tool(tickets, activity, as_of=None, stale_after_days=7) -> list[Verdict]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_crosstool_reconcile.py
def test_run_cross_tool_threads_as_of_for_stalled():
    tickets = {"SSSB-7": {"key": "SSSB-7", "status": "In Progress", "team": "Atlas"}}
    act = {"SSSB-7": Activity("SSSB-7", False,
                              [PR(20, "open", False, "t", "u", "2026-06-15T00:00:00Z")], 0, None)}
    verdicts = run_cross_tool(tickets, act, as_of="2026-06-25T00:00:00+00:00")
    assert verdicts[0].actual_status == "amber"
    assert not verdicts[0].is_watermelon
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_crosstool_reconcile.py::test_run_cross_tool_threads_as_of_for_stalled -v`
Expected: FAIL with `TypeError: run_cross_tool() got an unexpected keyword argument 'as_of'`.

- [ ] **Step 3: Add the params to `run_cross_tool`**

Replace `run_cross_tool` in `sprintsight/crosstool.py` with:

```python
def run_cross_tool(
    tickets: dict[str, dict[str, Any]],
    activity: dict[str, Activity],
    as_of: str | None = None,
    stale_after_days: int = 7,
) -> list[Verdict]:
    """Reconcile every Jira ticket against its GitHub activity (matched by key)."""
    return [
        reconcile({
            "ticket": ticket,
            "activity": activity.get(key),
            "as_of": as_of,
            "stale_after_days": stale_after_days,
        })
        for key, ticket in tickets.items()
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_crosstool_reconcile.py -v`
Expected: PASS (all reconciler tests, including the existing `test_run_cross_tool_flags_only_watermelons` which passes no `as_of`).

- [ ] **Step 5: Surface stalled separately in the demo script**

In `scripts/run_cross_tool.py`, add `from datetime import datetime, timezone` at the top. Replace the `verdicts = run_cross_tool(...)` line and the printing block at the end of `main()` with:

```python
    as_of = datetime.now(timezone.utc).isoformat()
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
```

- [ ] **Step 6: Add real `updated_at` to the sandbox capture (fidelity)**

In `data/captured/github_sandbox_live.json`, add `"updated_at"` to the two PR entries using the real values read live (these are fresh, so they will NOT be stalled, which is correct):

```json
  {"type": "pr", "number": 1, "title": "SSSB-2 dashboard spacing polish", "state": "open", "merged": false, "url": "https://github.com/davidmjackson/sprintsight-sandbox/pull/1", "updated_at": "2026-06-25T06:37:19Z"},
  {"type": "pr", "number": 2, "title": "SSSB-3 add export to CSV", "state": "closed", "merged": true, "url": "https://github.com/davidmjackson/sprintsight-sandbox/pull/2", "updated_at": "2026-06-25T06:37:26Z"},
```

- [ ] **Step 7: Smoke-run the demo offline**

Run: `python scripts/run_cross_tool.py --recorded data/captured/github_sandbox_live.json --jira-recorded data/captured/jira_SSSB_live.json`
Expected: prints `6 tickets checked, 2 watermelon(s), 0 stalled:` then the two watermelon blocks (SSSB-1, SSSB-2). No traceback. (Zero stalled is correct: the sandbox PRs are fresh.)

- [ ] **Step 8: Commit**

```bash
git add sprintsight/crosstool.py scripts/run_cross_tool.py data/captured/github_sandbox_live.json tests/test_crosstool_reconcile.py
git commit -m "feat(stage7): thread as_of through run_cross_tool + surface stalled in the demo [SS-5]"
```

---

### Task 5: Full gate, docs, and handover

**Files:**
- Modify: `HANDOVER.md`
- Modify: `docs/superpowers/specs/2026-06-25-stalled-signal-design.md` (status line)

- [ ] **Step 1: Run the whole suite + linter**

Run: `pytest -q && ruff check .`
Expected: all tests pass (the prior 207 plus the new stalled tests), ruff clean. Confirm the existing watermelon eval (4/4) and report eval (4/4) are unchanged.

- [ ] **Step 2: Update the spec status line**

Change the spec's `Status:` line to `BUILT (offline). Live not firable on a fresh repo; eval is the proof.` with today's date and the branch name `stage7-stalled-signal`.

- [ ] **Step 3: Update HANDOVER.md**

In the "Where we are" section, add a note: stalled (amber) signal built on branch `stage7-stalled-signal`; amber tier in `sprintsight/crosstool.py` for parked open PRs (default 7 days, configurable, injected `as_of`); 7/7 cross-tool eval; suite green; not live-demoable on a fresh repo (eval is the proof). Append one line to the `Learning queue` section: `amber tier / staleness via injected clock | a third verdict colour for "PR parked", measured against an injected as_of so the pure function stays deterministic | sprintsight/crosstool.py _stalled | 2026-06-25`.

- [ ] **Step 4: Commit**

```bash
git add HANDOVER.md docs/superpowers/specs/2026-06-25-stalled-signal-design.md
git commit -m "docs(stage7): handover + spec status for the stalled-signal slice [SS-5]"
```

---

## Self-review notes

- Spec coverage: `PR.updated_at` + read (Task 1); amber branch + `as_of`/threshold seams + boundary + back-compat (Task 2); eval cases 6-7 + doc (Task 3); `run_cross_tool` as_of + separate stalled surfacing (Task 4); full gate + docs (Task 5). All spec sections map to a task.
- `Verdict` reused; `detector.py` untouched; `is_watermelon` semantics unchanged; amber is surfaced separately.
- Type consistency: `PR.updated_at: str | None`, `_stalled(...) -> tuple[int, int] | None`, `run_cross_tool(..., as_of: str | None = None, stale_after_days: int = 7)`, evidence token `github:PR#<n>:stalled-<age>d` are identical across Tasks 1-4. The eval cases and unit tests use the same token format (`stalled-10d`).
