# CLAUDE.md — Sprintsight build manual (for Claude Code)

Operating manual for Claude Code when building Sprintsight. Build conventions only.
State lives in HANDOVER.md. Specs live in docs/. Must-follow rules are inlined below so
this file is self-sufficient (Claude Code does not see the planning thread's Project instructions).

## On startup, read in this order
1. HANDOVER.md (repo root) — current state, what is locked, what is next.
2. This file — how to build and how to drive the board.
3. The spec for the Story you are working (under docs/).

## Communicating with David (read this)
David is the product owner and is learning the AI-engineering concepts as we build. His
background is Agile delivery management, not senior engineering. He has been clear that
dense, senior-level write-ups leave him approving work he cannot follow, and we are
deliberately fixing that. Apply it here too:
- Explain before asking for a decision. Plain English first, one analogy, then the choice.
  Define every acronym on first use.
- Aim for understanding, not sign-off. He should be able to say a choice back in his own
  words. If a doc cannot be skim-read by a non-engineer, put a plain-English summary at the top.
- No em dashes in anything he reads (use commas, periods, or parentheses). Short paragraphs,
  tight bullets, lead with the verdict, end with clear next actions.
- Learning handoff (you flag, you do not write the log): LEARNING-LOG.md (repo root) is owned by
  the planning/training thread, which is its ONE writer. Do NOT edit LEARNING-LOG.md from here.
  When a Story introduces a genuinely NEW concept a non-engineer would need explained, append one
  line to the `Learning queue` section in HANDOVER.md (format: concept | one line on what is new |
  code/stage pointer | date). Flag only, do not teach. The training thread turns each flag into a
  log entry with David's restatement, then clears the line. This is how the product owner stays
  able to defend the work.

## What Sprintsight is (one line)
An AI delivery-intelligence layer that reads across delivery tools and produces audience-tuned,
fully-cited status reports, risk detection, and a watermelon detector (reported-green / actually-red).
Fuller context: sprintsight-braindump.md (held in Project knowledge; copy into the repo if needed here).

## Non-negotiable build principles
- Eval-first. No feature code before the eval it must pass exists. A feature Story with no eval is not Done.
- Security-first. Least data, least privilege. Flag every new data-persistence or external-call decision before it lands.
- Human-in-the-loop on anything that writes. RAID writes are recommend-only, never auto-write.
- Lean MVP. Tight scope, no gold-plating. Push back on scope creep.
- Document. Record decisions in ADRs / the brain dump. Keep HANDOVER.md current at the end of a session.

## Tech stack
- Backend: Python / FastAPI.
- Orchestration: LangGraph (Stage 3+), not full LangChain. Raw Anthropic SDK where clearer.
- Evals + observability: Langfuse. Evals are deterministic-first; LLM-as-judge deferred to Stage 4.
- Data / RAG: Postgres + pgvector.
- LLM: Anthropic API, structured outputs, ZDR on all client/data traffic.
- Agent graph: THREE nodes (retrieval, risk/reconciliation, report-writer). Planner, analysis, critic
  stay as functions/prompts until evals justify promoting them to nodes.

## Jira (project SS, team-managed)
Full rules: docs/jira/workflow.md. Must-knows:
- Statuses: Backlog -> To Do -> In Progress -> In Review -> Done. Blocked is a flag, not a status.
- WIP limit: 1 to 2 Stories in progress at once.
- Evals run in In Review. In Review -> Done needs all ACs met, evals green where the Story has them, docs updated.
- Reference issues by key. Reuse exact label spellings (stage-0..7, eval, security, decision, moat, data). No near-duplicates.
- Never skip In Review; never set Done on create.
- Drive the board via the Composio MCP (create, transition). Do not set status on create.
- Epic key map: docs/jira/epic-key-map.md. Foundation & De-risking = SS-3.

## Repo / docs map
- HANDOVER.md — current state (read first).
- docs/jira/workflow.md — board rules. docs/jira/epic-key-map.md — Epic-to-key map.
- docs/jira/sprintsight-build-items.json — the 17 issues as created.
- docs/data/data-strategy.md — SS-1.3 (scenario-first synthetic, four teams).
- docs/evals/watermelon-eval.md — SS-1.4. docs/evals/report-quality-eval.md — SS-1.5.
- docs/moat/moat-behaviours.md — SS-1.7 (the three methodology-aware behaviours).
- sprintsight-braindump.md — full project context (Project knowledge; not in repo by default).

## Do NOT do yet
- Do not generate the data corpus or write the eval harness until Stage 1 opens.
- Keep Stage 0 specs as paper specs.
- No feature code before its eval exists.

## Stage gate
Currently Stage 0 (Foundation, Epic SS-3). Stage 1 (ingestion + RAG core) starts only after the
Foundation Stories are Done.
