# Sprintsight — Jira Workflow (for Claude Code)

Reference rules for how Claude Code manages the SS board. Keep in repo at
`docs/jira/workflow.md` and reference from CLAUDE.md.

## Issue model
- **Epic** = stage container. No work logged directly on Epics.
- **Story** = the unit of work. Everything actionable is a Story, including chores.
- Story links to Epic via the **Parent** field (team-managed project SS).

## Statuses (Story)
Backlog -> To Do -> In Progress -> In Review -> Done
- **Blocked is a flag, not a status.** Flag the issue, comment the blocker, unflag when cleared.

## Transition rules
- **Backlog to To Do:** Story belongs to the active stage.
- **To Do to In Progress:** work started. WIP limit: 1 to 2 Stories in progress at once.
- **In Progress to In Review:** output complete, self-reviewed, evals run.
- **In Review to Done:** every AC checked; evals green where the Story has them; decisions log or brain dump updated where relevant.

## Definition of Done
A Story is Done only when:
1. All Acceptance Criteria in its description are met.
2. Any evals it owns pass. Eval-first: a feature Story with no eval is not Done.
3. Docs it touches are updated (ADR, brain dump, HANDOVER.md).

## Conventions for Claude Code
- Reference issues by key (for example SS-3) once keys exist, not by summary.
- Reuse exact label spellings already in the instance: stage-0 to stage-7, eval, security, decision, moat, data. Never create a near-duplicate.
- Move one status step at a time and report each transition.
- Priority is not used for ordering. Sequence is driven by the board and the WIP limit.
- Never set a Story to Done on creation, and never skip In Review.

## Active stage
- Stage 0 = Epic "Foundation & De-risking" (key SS-3). Only its Stories are detailed.
- Other Epics stay empty until their stage opens.
- Highest-leverage Stage-0 Stories: data strategy first, then the two eval specs.

## Epic key map
Canonical Epic-to-key map lives in `docs/jira/epic-key-map.md`. Regenerate from Jira whenever Epics change.