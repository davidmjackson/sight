# ADR-0001: Cut the agent graph to three nodes for the showcase

- **Story:** SS-1.6
- **Status:** Accepted
- **Date:** 2026-06-17
- **Deciders:** David (owner)

## Context

The brain dump (section 10) proposed a six-agent graph: planner, retrieval, risk, analysis, report-writer, and a critic/eval hook. That was specified before any evals existed.

Three things pull against six nodes for the showcase:

1. **Eval-first principle.** Architecture should follow evaluation results, not precede them. Nothing yet shows that planning, analysis, or criticism each need to be an independent node with its own state and tracing.
2. **Solo, lean MVP.** Every LangGraph node is orchestration surface to build, test, trace, and maintain. Six nodes is over-engineered for a one-person showcase at Stage 3.
3. **Reversibility is cheap.** Promoting a function to a node later is low cost if node boundaries are kept clean. Demoting an over-built node is wasted effort now.

## Decision

The Stage 3 LangGraph graph has **three nodes**:

- **retrieval** (pulls and ranks artifacts, returns cited chunks)
- **risk / reconciliation** (extracts risks, reconciles against the RAID log, recommend-only)
- **report-writer** (audience-tuned output: team / programme / exec)

**Planner, analysis, and critic stay as functions or prompts** inside or around those nodes. They are not graph nodes until an eval result justifies promoting them.

## Consequences

**Positive**
- Less to build, test, and trace at Stage 3. Faster path to the first multi-agent demo.
- Decisions are deferred until there is evidence, which is itself the showcase point (eval-driven architecture).
- Matches the three hero screens and the Stage 2 to 4 build targets.

**Negative / risks**
- If planning logic grows complex, it may need promotion to a node later. Mitigation: keep node boundaries clean so promotion is a refactor, not a rewrite.
- The critic starts as an inline eval hook rather than a node. Mitigation: the eval harness (Stage 1+) and Langfuse tracing (Stage 4) cover validation until a node is justified.

## Revisit triggers

Promote a function to a node when an eval shows it needs **any** of:
- independent state across the graph,
- its own tracing boundary for debugging or cost attribution,
- a human-in-the-loop checkpoint of its own.

## Links

- Brain dump sections 10 (agent architecture) and 13 (framework decision).
- CLAUDE.md tech stack (three-node rule inlined there).
- Watermelon eval SS-1.4 and report-quality eval SS-1.5 are the evidence sources that would justify promotion.
