# Sprintsight — Stage 1 Stories (Ingestion + RAG Core, Epic SS-2)

Created 2026-06-17 (Claude Code). All Stories live under Epic **SS-2** (Ingestion + RAG Core),
label `stage-1`, status Backlog. Sequenced eval-first: the eval and its fixtures land before the
feature code they gate. WIP limit 1–2.

> Note: the SS-2.x shorthand is planning-only. Real Jira keys were scrambled by parallel creation
> (same as the Foundation batch). Verify against Jira before acting. See also
> [docs/jira/epic-key-map.md](epic-key-map.md) and the workflow rules in [workflow.md](workflow.md).

## Story → key map

| Shorthand | Jira key | Summary | Labels | Depends on |
|-----------|----------|---------|--------|------------|
| SS-2.1 | SS-19 | Generate synthetic corpus + ground-truth labels | `data` `stage-1` | — (unblocks all) |
| SS-2.2 | SS-21 | Eval harness skeleton + Langfuse wiring | `eval` `stage-1` | SS-2.1 |
| SS-2.3 | SS-18 | Implement watermelon eval (SS-1.4), 4 cases | `eval` `moat` `stage-1` | SS-2.1, SS-2.2 — lands red |
| SS-2.4 | SS-20 | Schema → migrations: artifact/chunk/signal + pgvector | `security` `stage-1` | — |
| SS-2.5 | SS-24 | Ingestion pipeline: parse → chunk → embed(1024) → store | `stage-1` | SS-2.1, SS-2.4 |
| SS-2.6 | SS-23 | RAG retrieval (ADR-0001 retrieval node) | `stage-1` | SS-2.5 |
| SS-2.7 | SS-22 | Baseline watermelon detector (turns SS-1.4 green) | `moat` `stage-1` | SS-2.3, SS-2.6 |

## Eval-first build order

1. **SS-2.1** corpus + ground-truth labels (fixtures everything else needs).
2. **SS-2.2** + **SS-2.4** in parallel (eval harness / DB migrations — independent).
3. **SS-2.3** watermelon eval — lands **red** (no detector yet), proving the gate bites.
4. **SS-2.5** ingestion → **SS-2.6** retrieval.
5. **SS-2.7** baseline detector — turns SS-2.3 **green** (4/4 classification, 4/4 evidence).

## Scope decisions (confirmed with owner 2026-06-17)

- **SS-1.5 report-quality eval** is NOT a Stage-1 story. It grades the Stage-2 status-report agent,
  so it becomes the eval-first opener of **Stage 2 (Epic SS-1)**. The generic harness (SS-2.2) is
  built so SS-1.5 plugs in cheaply there.
- **SS-2.7 detector is logic only** — the SS-1.4 eval needs something under test to be a real gate.
  The full portfolio / watermelon UI stays in **Stage 6 (Epic SS-6)**.
- Detector is **recommend-only** (never auto-writes to the RAID log), per the locked moat principle B3.
