# Design: Stalled-PR signal (amber) for the cross-tool reconciler

Status: DESIGNED (2026-06-25). Not yet built. Stage 7 follow-up to Goal B. Epic SS-5 (UX Polish +
Connectors). Author: Claude Code + David.
Process: superpowers brainstorming -> writing-plans -> eval-first build -> review.
Builds directly on the cross-tool watermelon (Goal B, merged @ 7c3ab55):
docs/superpowers/specs/2026-06-25-cross-tool-watermelon-design.md.

## Plain-English summary (read this first)

The cross-tool detector is binary today: a ticket that claims progress either has code (green) or
has none (red watermelon). This slice teaches it a third colour, **amber = "there is a pull request,
but it has been parked"**: an open PR that nothing has touched in 7 days. Amber is a softer flag.
It is surfaced in its own list and is never called a watermelon (that word stays reserved for the
clear red cases).

The proof is the offline eval. Unlike the watermelon, the stalled signal cannot be shown on a live
demo today, because the sandbox PRs are minutes old and GitHub timestamps cannot be backdated. It
will fire for real once a PR genuinely ages past the threshold.

## Locked decisions

1. **Amber is a warning, NOT a watermelon.** `actual_status` gains the value `amber`;
   `is_watermelon` stays red-only (reported green AND actual red). Amber tickets get
   `is_watermelon = False` and are surfaced in a separate "stalled" list.
2. **Stale after 7 days, configurable.** Threshold defaults to 7 days, readable from inputs so it
   can be tuned per run without a code change.
3. **Freshness source = the open PR's `updated_at`** (always present, models "PR parked"), with
   `Activity.last_commit_at` as a secondary signal. Stale only if the freshest of the two is older
   than the threshold.
4. **Amber applies ONLY to In Progress / In Review tickets that have an open PR.** The existing
   red rules (no work; Done without a merged PR) and green rules (Done + merged) are untouched.
5. **Pure + injected seams.** The reference "now" (`as_of`) and `stale_after_days` come in via the
   reconciler inputs, never `datetime.now()`, so the function stays pure and deterministic. When
   `as_of` is absent the staleness check is skipped, so the existing 5 cross-tool eval cases keep
   passing unchanged.
6. **Eval-first.** New eval cases for stalled (amber) and fresh (green) land before the logic.

## Architecture

Three small changes, all additive. No change to the watermelon (red) rules.

### A. Data shape (`sprintsight/connect/github.py`)

Add one optional field to `PR`:

```python
@dataclass(frozen=True)
class PR:
    number: int
    state: str
    merged: bool
    title: str
    url: str
    updated_at: str | None = None   # GitHub's PR last-activity timestamp
```

`fetch_github` reads `pr.updated_at` into the clean item. `index_activity` already carries PRs
through unchanged (it passes the dict fields into `PR`); it gains `updated_at` in the mapping. The
captured replay files gain the field. `Activity.last_commit_at` is unchanged.

### B. The reconciler (`sprintsight/crosstool.py`)

A new middle branch in `reconcile`, reached only for In Progress / In Review tickets that have an
open PR:

- freshest = newest of (the newest open PR's `updated_at`, `Activity.last_commit_at`), among those
  present. If any open PR is fresh, the work is alive, so only the most recently updated open PR
  matters; the cited PR number is that newest open PR.
- If freshest is present and `(as_of - freshest) >= stale_after_days` -> `actual = "amber"`,
  evidence token `github:PR#<n>:stalled-<age>d`.
- Otherwise -> `green` (active), exactly as today.

`reconcile` reads `as_of = inputs.get("as_of")` and `stale_after_days = inputs.get(
"stale_after_days", 7)`. If `as_of` is None, the staleness branch is skipped (has-work -> green),
preserving today's behaviour. Timestamps are parsed tolerantly (ISO 8601, `Z` suffix handled on
Python 3.11+); a `<n>d` age is the floor of the day difference.

`is_watermelon` is unchanged: `reported == "green" and actual == "red"`. Amber -> `False`.

### C. Surfacing (`run_cross_tool` consumers)

`run_cross_tool` still returns one `Verdict` per ticket. The demo script splits the results into
two lists when printing: watermelons (`actual_status == "red"` and `is_watermelon`) and stalled
(`actual_status == "amber"`), so the two are never conflated.

### Data flow (unchanged shape, one new branch)

```
Jira ticket {key,status} + GitHub Activity{key} + as_of
   -> reconcile(...)
       red   : no work / Done-not-merged      (watermelon, unchanged)
       amber : In Progress/Review, open PR parked >= 7d   (NEW, not a watermelon)
       green : active / shipped
   -> watermelons list (red) + stalled list (amber)
```

## Testing (eval-first)

New cases appended to `sprintsight/evals/crosstool_eval.py` (the existing 5 stay green, untouched,
because they set no `as_of`). All run offline with a fixed `as_of`:

| Case | Jira status | GitHub activity                       | Verdict            | Required evidence |
|------|-------------|---------------------------------------|--------------------|-------------------|
| 6    | In Progress | open PR #20, `updated_at` 10 days ago | amber / stalled    | jira-KEY, github:PR#20:stalled-10d |
| 7    | In Progress | open PR #21, `updated_at` 1 day ago   | green (not flagged)| (none) |

The dual gate carries over (classification: `actual=amber, is_watermelon=False`; evidence: the
stalled token must be cited). A unit test pins the boundary explicitly: age `>= 7` days is stalled,
age `< 7` is green. A unit test confirms an absent `as_of` skips the check (back-compat). The eval
doc `docs/evals/cross-tool-watermelon-eval.md` gains a "Stalled (amber)" section describing cases
6-7.

## Security and scope (security-first flags)

- No new external call, no new secret, no writes. Read-only holds. The only data change is one
  extra read-only field already returned by the GitHub PR read.
- **In scope:** `PR.updated_at`, the amber/stalled branch, the `as_of` + `stale_after_days` seams,
  the separate stalled list in the demo, 2 eval cases + boundary + back-compat unit tests.
- **Out of scope (YAGNI):** per-team rollup; surfacing amber in the web UI (a separate deferred
  slice); any change to the watermelon (red) rules; branch-only freshness (no timestamp to
  measure); a live demo of stalled (not firable on a fresh repo; the eval is the proof).

## Out of scope

- The web UI, the burndown detector, retrieval, ingest, the report writer: all untouched.
- Writing to GitHub or Jira.
- Backdating or seeding aged PRs to force a live stalled flag.
