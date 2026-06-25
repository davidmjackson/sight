# Design: Second connector + live cross-tool watermelon (Goal B)

Status: BUILT (offline), live-verify pending (2026-06-25, branch `stage7-cross-tool-watermelon`,
not yet merged). GitHub connector + pure reconciler + 5/5 cross-tool eval; full suite 205 passed
+ 3 skipped, ruff clean. Plan: docs/superpowers/plans/2026-06-25-cross-tool-watermelon.md.
Stage 7 third slice. Epic SS-5 (UX Polish + Connectors). Author: Claude Code + David.
Process: superpowers brainstorming -> writing-plans -> eval-first build -> review -> live-verify.
Builds directly on the Jira connector (Goal A, merged @ d5945dc):
docs/superpowers/specs/2026-06-24-jira-connector-design.md.

## Plain-English summary (read this first)

Goal A proved we can read ONE live tool (Jira) and turn its tickets into something the app
reasons over. Goal B is the payoff: read a SECOND live tool (GitHub) and catch a watermelon that
no single tool could see.

The watermelon we are hunting is "status versus activity." A Jira ticket says it is progressing
(In Progress, In Review, or Done), but GitHub shows the truth: there is no code work for it, or it
was called Done while its pull request is still open and unmerged. Reported looks healthier than
reality. That is a watermelon, and it only shows up when you cross-check two tools.

We add a GitHub connector (read-only) and a small new reconciler. The existing watermelon detector
and the whole retrieval pipeline are left untouched. We prove it offline first with an eval, then
live against the real SSSB Jira board plus a seeded demo GitHub repo.

## Locked decisions

1. **Goal B** = second connector + live cross-tool watermelon. The bigger moat.
2. **Second tool = GitHub**, read-only. It is the "what actually happened" side; Jira is the
   "what was reported" side.
3. **Detection unit = per-ticket.** One watermelon is one Jira ticket cross-checked against its
   GitHub activity. No team rollup in this slice.
4. **The red rule (the watermelon condition), v1 = two clean cases:**
   - Claims progress (In Progress / In Review / Done) but NO branch, PR, or commit references the
     ticket key. The headline signal.
   - Says Done but its linked PR is still open / unmerged. "Called finished, not shipped."
5. **Jira-to-GitHub join = the ticket key** appearing in a branch name, PR title, or commit
   message (the standard convention). We control the demo repo so we can guarantee it.
6. **New focused reconciler, existing detector untouched.** The Jira-to-GitHub link is a factual
   join on the key, not a fuzzy text match, so it does NOT belong in the embedding / RAG pipe.
   `sprintsight/detector.py` and the existing CI gates are not edited.
7. **Eval-first, network walled off.** The reconciler is a pure function tested entirely offline.
   Live proof runs via captured replay, exactly like the Jira slice.

## Architecture

Two new units plus a thin orchestrator. Same seam style as the Jira connector.

### A. `GitHubConnector` (new file `sprintsight/connect/github.py`)

Mirrors `JiraConnector`. The network-risky part is tiny and isolated.

1. **`fetch_github(repo) -> list[dict]`** is the ONLY piece that touches the network. It pulls the
   repo's branches, pull requests, and commits as raw dictionaries. Lazy-imported client,
   injectable, so a flaky network affects nothing else and no test calls it.
2. **`index_activity(items) -> dict[str, Activity]`** is a PURE function. It scans each branch
   name, PR title, and commit message for a Jira key (e.g. "SSSB-4") and groups the facts under
   that key. This is the real new connector logic and is hard-tested.
3. **`GitHubConnector.fetch_activity() -> dict[str, Activity]`** ties them together and implements
   a small protocol so an offline twin (reads a saved sample) can stand in for tests.

`Activity` is a small structured fact per ticket key, just enough for the two red rules:

```python
@dataclass(frozen=True)
class Activity:
    key: str                    # "SSSB-4"
    has_branch: bool
    prs: list[PR]               # PRs whose title/branch/commit references this key
    commit_count: int
    last_commit_at: str | None  # carried for the future "stalled" rule; unused in v1
```

where `PR` is `{number, state, merged, title, url}`.

### B. `reconcile(ticket, activity) -> Verdict` (new file `sprintsight/crosstool.py`)

A PURE function, the heart of the slice. Reuses the existing `Verdict` contract
(`sprintsight/evals/watermelon.py`), so nothing downstream needs a new shape.

- **reported_status** from the Jira status: In Progress / In Review / Done all mean "claiming
  progress" = green. To Do / Backlog mean "not claiming anything" and can never be a watermelon.
- **actual_status** from the GitHub activity:
  - claims progress but no linked work at all = red
  - claims Done but no merged PR = red
  - otherwise (work exists and matches the claim) = green
- **is_watermelon** = reported is green AND actual is red (reported healthier than reality, the
  same rank rule as the existing detector).
- **evidence** cites both sides: the Jira artifact id (`jira-SSSB-4`) and a GitHub reference token
  (e.g. `github:no-ref:SSSB-4` or `github:PR#12:open-unmerged`). A watermelon that fails to cite
  both sides fails the eval.

v1 uses only green and red. Amber stays reserved for the deferred "stalled for N days" signal, so
we do not commit to a day-threshold now.

### C. `run_cross_tool(jira_connector, github_connector)` orchestrator (in `crosstool.py`)

Fetches Jira tickets and GitHub activity, runs `reconcile` per ticket, returns the verdicts. Both
connectors are injectable, so the same function runs live or from captured replay.

### Data flow

```
Jira connector   -> tickets {key, status}
GitHub connector -> activity {key -> Activity}
                       |
       per ticket: reconcile(ticket, activity[key]) -> Verdict
                       |
             keep is_watermelon=True -> cited cross-tool report
```

The Jira connector and the whole retrieval / ingest pipeline already exist. The genuinely new
brainpower is one pure indexer plus one pure reconciler.

## Testing (eval-first, our non-negotiable)

New eval spec `docs/evals/cross-tool-watermelon-eval.md`, run through the existing harness
(`run_suite`) with the same DUAL GATE as today's watermelon eval: a case passes only when the
label is right AND the required evidence is cited. The "lucky guess" blocker carries over: a
verdict with the right label but no GitHub evidence still fails.

Five hand-built `(ticket, activity)` fixture pairs:

| Case | Jira says   | GitHub shows           | Verdict           | Why it is in the set            |
|------|-------------|------------------------|-------------------|---------------------------------|
| 1    | In Progress | nothing references key | watermelon (red)  | The headline. Never miss it.    |
| 2    | Done        | PR open, unmerged      | watermelon (red)  | "Called finished, not shipped." |
| 3    | In Progress | open PR + commits      | honest (green)    | Must NOT flag real work.        |
| 4    | Done        | PR merged              | honest (green)    | Decoy: a PR exists but is merged.|
| 5    | To Do       | nothing                | not a watermelon  | Guard: a backlog ticket is not lying.|

The reconciler is pure, so every case is tested offline with no network. CI stays fully offline:
it reads fixtures, never calls GitHub. The live fetch is exercised only by the demo script.

## Live-verify (Goal B's actual proof)

Same pattern as the Jira slice:

1. Seed a **demo GitHub repo** (a throwaway, e.g. `sssb-demo`, NOT this build repo) with branches
   and PRs that reference the real SSSB Jira keys, deliberately arranged so at least one ticket is
   a true cross-tool watermelon (Done with an open PR) and one is honest.
2. Run both connectors LIVE, capture the GitHub read to `data/captured/github_<repo>_live.json`
   (replay file, mirrors `jira_SSSB_live.json`).
3. Produce a cited cross-tool watermelon report from real Jira plus real GitHub. That is the moat
   moment: a watermelon no single tool could see.

Decision deferred to verify time (flagged, not a surprise): which repo to seed, and whether to
seed via the GitHub MCP or by hand.

## File layout

- `sprintsight/connect/github.py` — connector, `Activity`, `PR`, pure `index_activity`, walled `fetch_github`
- `sprintsight/crosstool.py` — `reconcile()` + `run_cross_tool()` orchestrator
- `docs/evals/cross-tool-watermelon-eval.md` — the eval spec
- `tests/test_github_connector.py`, `tests/test_crosstool_reconcile.py`, `tests/test_cross_tool_eval.py`
- `scripts/run_cross_tool.py` — CLI demo, supports `--recorded`
- `data/captured/github_<repo>_live.json` — captured replay

**Reused unchanged:** the `Verdict` contract, the eval harness, the Jira connector, ingest, retrieval.
**Untouched:** `detector.py` and the existing CI gates.

## Security and scope (security-first flags)

- The GitHub connector is **read-only**. It never writes to GitHub or Jira. Recommend-only holds.
- **Least data**: pull only the demo repo's branches, PRs, and commits, only the fields we map.
- **New external call (flagged)**: the GitHub API. Least-privilege, read-only token.
- **New data file (flagged)**: one captured replay of public repo metadata, low sensitivity.
- **Deferred** (not this slice): the "stalled for N days" signal; per-team rollup; pushing GitHub
  through RAG; the app-side Composio SDK path still unrun from Goal A; multi-tenant `team_id`;
  persistent Supabase. See the offline-standins notes.

## Out of scope

- Any change to chunking, embedding, retrieval, the existing burndown detector, or the report writer.
- Any web UI change (surfacing live cross-tool watermelons in the portfolio screens is a later slice).
- Writing to GitHub or Jira from the app.
- A third connector, or any signal beyond the two red rules above.
