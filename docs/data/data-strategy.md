# Sprintsight — Demo Data Strategy (SS-1.3)

Status: LOCKED 2026-06-17 (roster shipped). Satisfies SS-1.3. Feeds SS-1.4 (watermelon eval),
SS-1.5 (report eval), and SS-1.7 (moat behaviours). Repo path: docs/data/data-strategy.md

## 1. Method (recommended)
Scenario-first synthetic. Three steps:
1. Author the ground truth by hand (the design below). This is the high-value IP and where your Agile expertise lives.
2. Generate the surface artifacts (status reports, RAID entries, chat, ticket/burndown summaries) with an LLM, from the ground truth.
3. Curate: edit for realism, add decoy noise, verify every seeded signal is present and every ground-truth label is supported by an artifact.

Why not reshape real history: one person's data will not yield several genuinely divergent teams, and it drags in anonymisation risk. Why not pure hand-authoring: slow, and weaker natural-language texture than an LLM gives.

## 2. Anonymisation
Fully synthetic. Fictional team and person names, no real client data. This satisfies the anonymisation requirement by construction and avoids the compliance jump for the showcase.

## 3. Team roster (the ground truth)
Four teams, two sprints (Sprint 14 and Sprint 15), giving trend plus contrast. Each team is purpose-built.

### Team Atlas — the WATERMELON (hero case)
- Reported: Green, Green.
- Actual: Amber drifting Red.
- Seeded signals:
  - Burndown flat across both sprints (commits ~40pts, burns ~12). Scope not really moving.
  - Velocity down ~30 percent sprint on sprint.
  - A vendor / cross-team API dependency on Team Draco slipping, raised by a dev in chat ("heads up, Draco's auth API still isn't ready, this will bite us") but never logged in the RAID.
  - Carry-over stories growing 2 -> 5.
  - Status report text: "on track, minor items only".
- Ground truth: RED. is_watermelon: true.
- Moat behaviours exercised: flat_burndown_vs_green, risk_in_chat_not_raid, cross_team_dependency_slip.

### Team Boreas — TRUE GREEN (false-positive guard)
- Reported: Green, Green.
- Actual: Green.
- Signals: burndown tracking to plan, RAID current with owners and mitigations, stable velocity.
- Ground truth: GREEN. is_watermelon: false.
- Purpose: the system must NOT flag this. Guards precision.

### Team Cygnus — HONEST AMBER
- Reported: Amber, Amber.
- Actual: Amber.
- Signals: openly flags a dependency slip and a resourcing gap in BOTH the status report and the RAID. Burndown shows the slip honestly.
- Ground truth: AMBER. is_watermelon: false (reported matches actual).
- Purpose: the system must agree with honest amber, not "watermelon" a truthful report. Tests it distinguishes reported-amber-and-actually-amber (fine) from reported-green-and-actually-amber (watermelon).

### Team Draco — TRICKY NEAR-MISS
- Reported: Green then Amber.
- Actual: Amber.
- Signals: one alarming-looking signal (a late-sprint bug spike) that is actually under control (triaged, burndown still OK, risk logged). Looks like it might be a watermelon but resolves to amber.
- Also the counterpart of the Atlas dependency: Draco's auth API slip is real and visible in Draco's own data, which is how the cross-team link can be reconciled.
- Ground truth: AMBER. is_watermelon: false (near-miss).
- Purpose: the "tricky near-miss" eval case. The system must NOT call this a watermelon despite the scary signal. Guards precision.

## 4. The cross-team thread
Atlas depends on Draco's auth API. Draco slips it. Atlas does not surface the risk and keeps reporting green. This single thread:
- Makes the watermelon real (not just a flat burndown in isolation).
- Demonstrates cross-team reasoning (the differentiator vs walled-garden tools).
- Is reconcilable from data: the slip shows in Draco's artifacts and in one Atlas chat message, but is absent from Atlas's RAID and status report.

## 5. Artifacts per team per sprint
- 1 status report (the reported RAG and narrative).
- RAID log entries (current state of risks/issues/deps).
- A ticket/burndown summary (the actual signal: committed vs done, velocity, carry-over).
- Chat snippets (where hidden signals and decoy noise live).
- Decoy noise: irrelevant chatter and normal tickets, so signals are not trivially findable.

## 6. Ground-truth label schema (eval-consumable)
One record per team per sprint. Machine-readable (YAML or JSON). Example:

```yaml
- team: Atlas
  sprint: 15
  reported_status: green
  actual_status: red
  is_watermelon: true
  divergence_reasons:
    - flat_burndown_two_sprints
    - vendor_dependency_slip_unlogged
    - velocity_decline_30pct
  moat_behaviours:
    - flat_burndown_vs_green
    - risk_in_chat_not_raid
    - cross_team_dependency_slip
  expected_evidence:
    - artifact_id: slack-atlas-s15-msg-dep   # the "Draco auth not ready" message
    - artifact_id: burndown-atlas-s15        # flat burndown
    - artifact_id: status-atlas-s15          # the "on track" claim
```

## 7. How this maps to evals and the moat
- SS-1.4 watermelon eval: each team/sprint becomes a case. Atlas = true watermelon, Boreas = true green, Cygnus = true amber, Draco = tricky near-miss. Pass = correct classification AND cites the expected_evidence, not just the label.
- SS-1.5 report eval: generate a status report for a team and assert every claim traces to an artifact; include a thin-data trap so the agent must decline to fabricate.
- SS-1.7 moat: the three behaviours are seeded into Atlas (and reconciled against Draco), so they are demonstrable and testable, not just asserted.

## 8. Believability checklist (curation pass)
- Each seeded signal is present in at least one artifact.
- Each ground-truth label is supported by a citable artifact.
- Decoy noise added so signals are not the only content.
- Status reports read like real PM prose, not labelled "this is the watermelon".
- Numbers are internally consistent across burndown, velocity, and carry-over.

## 9. What this unblocks
- SS-1.4 and SS-1.5 can be written against concrete cases.
- SS-1.7 has real material to define behaviours against.
- Stage 1 ingestion has a real corpus to parse, embed, and cite.
- SS-7 (Portfolio + Watermelon) has its demo dataset ready.
