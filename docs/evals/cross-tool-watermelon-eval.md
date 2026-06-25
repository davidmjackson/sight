# Cross-tool watermelon eval (Goal B, SS-5)

Per-ticket "status versus activity" watermelon: Jira says a ticket is progressing, GitHub shows
no work for it, or it was called Done with an unmerged PR. Reuses the SS-1.4 `Verdict` contract
and the deterministic harness, dual-gated exactly like the team watermelon eval:

- classification: `is_watermelon` AND `actual_status` must equal the ground truth.
- evidence: every required token must appear in the verdict's `evidence` list.

A case passes only when BOTH gates pass. Subject under test: `reconcile(inputs) -> Verdict`,
`inputs = {"ticket": {key, status, team}, "activity": Activity | None}`. Until `reconcile`
exists, `null_reconciler` abstains so the suite is RED (the eval-first signal).

## Cases

| Case | Jira status | GitHub activity        | is_watermelon | actual | Required evidence |
|------|-------------|------------------------|---------------|--------|-------------------|
| 1    | In Progress | none                   | true          | red    | jira-SSSB-1, github:no-ref:SSSB-1 |
| 2    | Done        | PR #12 open, unmerged  | true          | red    | jira-SSSB-2, github:PR#12:open-unmerged |
| 3    | In Progress | PR #5 open + 3 commits | false         | green  | (none) |
| 4    | Done        | PR #8 merged           | false         | green  | (none) |
| 5    | To Do       | none                   | false         | green  | (none) |

Cases 4 and 5 are the false-positive guards: a merged PR is healthy, a backlog ticket is not lying.

## Stalled (amber)

A ticket claiming progress with an open PR that has gone quiet (no PR/commit activity for
`stale_after_days`, default 7, measured against an injected `as_of`) is flagged **amber /
stalled** - a warning, not a watermelon (`is_watermelon` stays False). Boundary: age >= 7 days
is stalled, age < 7 is green. When `as_of` is absent the check is skipped (back-compat).

| Case | Jira status | GitHub activity                  | actual | Required evidence |
|------|-------------|----------------------------------|--------|-------------------|
| 6    | In Progress | open PR #20, updated 10 days ago | amber  | jira-SSSB-7, github:PR#20:stalled-10d |
| 7    | In Progress | open PR #21, updated 1 day ago   | green  | (none) |
