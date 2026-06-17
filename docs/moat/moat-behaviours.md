# Sprintsight — Moat Spec: Methodology-Aware Behaviours (SS-1.7)

Status: LOCKED 2026-06-17 (three behaviours confirmed by David). Satisfies SS-1.7. Paper spec, no code.
Depends on SS-1.3 roster (behaviours are seeded into Atlas/Draco).
Referenced by SS-1.4 and SS-1.5. Repo path: docs/moat/moat-behaviours.md

## 1. The thesis
Generic RAG-over-docs retrieves and summarises what a document says. Sprintsight
reasons about the delivery PROCESS behind the documents. The difference is encoded
in three behaviours below. Each requires understanding Agile delivery mechanics, not
just text similarity. That understanding is the moat: it is hard to copy and it is
what walled-garden, single-tool products structurally cannot do.

Each behaviour is defined by: trigger, expected action, why it is methodology-aware
(the contrast vs generic RAG), how it is evaluated, and the use case it serves.

## 2. Behaviour 1 — Cross-team dependency slip
- Trigger: Team A's delivery depends on Team B; B's artifacts show the dependency slipping; A's own status does not reflect the slip.
- Expected action: surface the cross-team risk in A's view, naming both teams and the slipping item, with citations to both sides.
- Why methodology-aware: requires reconciling artifacts ACROSS teams and tools, and understanding that a dependency is a delivery construct with an owner and a due point. Generic RAG retrieves within one team's docs and never crosses the boundary.
- Contrast test:
  - Generic RAG asked "is Atlas on track?": reads Atlas's status, answers "yes".
  - Sprintsight: reconciles Atlas's plan against Draco's slipping auth API, answers "no, a cross-team dependency is slipping and is not in Atlas's status".
- Evaluated by: SS-1.4 Atlas case (must cite the Draco dependency and reconcile across teams).
- Use case: 3 (portfolio roll-up) and 2 (risk radar).
- Seeded in: Atlas depends on Draco's auth API; Draco slips it.
- Decision (LOCKED): in scope, and not to be cut. This cross-team reconciliation is the differentiator vs walled-garden, single-tool products.
- Scope guardrail (LOCKED): reconcile discoverable dependencies only (a dependency named in an artifact, like the Atlas chat naming Draco's auth API), not inferred links. No general dependency-graph engine for the showcase. Keeps the behaviour demonstrable without gold-plating.

## 3. Behaviour 2 — Flat burndown vs reported on-track
- Trigger: burndown is flat or velocity is declining across sprints, while the status report claims green / on-track.
- Expected action: flag the divergence as a likely watermelon, citing the burndown and the contradicting status claim, and explain the gap.
- Why methodology-aware: requires reading a burndown and velocity as delivery signals (knowing that flat burndown means scope is not moving) and comparing them against the narrative. Generic RAG treats the status report as ground truth and parrots "on track".
- Contrast test:
  - Generic RAG: summarises the green status report at face value.
  - Sprintsight: notices the data contradicts the narrative and says so.
- Evaluated by: SS-1.4 Atlas case (correct red classification + cites burndown and the on-track claim).
- Use case: 3 (watermelon detector).
- Seeded in: Atlas burndown flat across two sprints with a green status report.
- Decision (LOCKED): compute the signals as facts, set transparent reference thresholds, and let the agent reason over them. Avoid both extremes — a pure-LLM "vibe" judgement is flaky, and a single magic cutoff is brittle and gameable.
  - Signals (computed deterministically per team per sprint): burn ratio = completed / committed points; velocity delta vs prior sprint; carry-over growth.
  - Reference thresholds (tunable, not hard gates — they cue the agent, they do not decide alone): burn ratio sustained below ~0.4 across two sprints = "flat"; velocity decline of ~25-30% or more sprint-on-sprint = "declining"; carry-over roughly doubling (e.g. 2 -> 5) = "growing".
  - These are derived from the Atlas seeded data (SS-1.3) and are reference values; they are published/transparent so they can be audited and tuned, never hidden.

## 4. Behaviour 3 — Risk raised in chat, missing from the RAID
- Trigger: a risk or issue raised in chat/Slack has no corresponding entry in the RAID log.
- Expected action: surface it as an unlogged risk and recommend logging it. Writing to the RAID requires human-in-the-loop confirmation.
- Why methodology-aware: requires understanding the RAID as a governance process (risks must be logged, owned, mitigated) and detecting the GAP between informal signal and formal record. Generic RAG has no concept of "should this have been logged".
- Contrast test:
  - Generic RAG: if asked, summarises the RAID as written. The chat risk is invisible because it was never logged.
  - Sprintsight: cross-references chat against the RAID and flags the missing risk.
- Evaluated by: SS-1.4 Atlas case (cite the chat message absent from RAID); future risk-radar eval at Stage 3.
- Use case: 2 (risk radar / RAID hygiene).
- Seeded in: Atlas's Draco-dependency risk raised in chat, never logged in RAID.
- Decision (LOCKED): recommend-only. The agent surfaces and recommends; it never auto-writes to the RAID. This is a permanent product principle (human stays accountable for the governance record), not a showcase-stage limitation.

## 5. Why these three together
They cover the three ways delivery truth hides: across team boundaries (1), behind a
reassuring narrative (2), and in informal channels outside governance (3). Each maps
to a seeded condition in Atlas, so each is demonstrable in the hero demo and testable
in the watermelon eval. They are the concrete content of "genuine Agile delivery
expertise encoded into the logic".

## 6. Coupling note
These behaviours are seeded into the Atlas/Draco data (SS-1.3). Changing a behaviour
means updating the data strategy and the watermelon eval to match. For the showcase,
ship these three. Additional behaviours (for example sprint-health prediction, scope
creep detection) are future work with their own seeded data and evals.

## 7. What this unblocks
- SS-1.4 and SS-1.5 have a named moat to test against (the behaviours are the "why" behind the eval cases).
- Stage 3 risk agent and Stage 6 watermelon analysis have a concrete behaviour spec.
- The contrast tests double as demo script material (generic RAG vs Sprintsight, side by side).
