---
artifact_id: raid-draco-s15
source_type: raid
source_ref: DRACO-RAID-S15
title: "Draco — RAID Log (Sprint 15)"
author: "Tomás Ferreira (Delivery Lead)"
source_timestamp: 2026-05-29T17:15:00Z
team: Draco
sprint: 15
---

# Draco RAID — Sprint 15

Reviewed at sprint close 2026-05-29. Sprint status: amber. Two items drive the amber call — a late
bug spike (triaged, under control) and the Auth API v2 slip. Both are owned and openly tracked.

## Risks

### R-DRACO-15-01 — Late-sprint bug spike on the v2 auth surface
- **Type:** Quality
- **Owner:** Rui Santos (QA Lead)
- **Status:** Open (mitigated)
- **Description:** 18 bugs were raised in the back third of the sprint (cluster DRACO-BUGSPIKE-S15),
  surfaced by the new contract-test harness (DRACO-421). All 18 triaged same-day (triage-draco-s15):
  predominantly low/medium severity (cosmetic, validation-message, docs-mismatch). No high/critical
  open; two mediums already fixed.
- **Impact:** Cost a few points of velocity (29 vs 33 last sprint); burndown stayed broadly on track.
  Remaining low-severity cleanup carried as DRACO-425.
- **Mitigation:** Severity-sort complete; lows batched into DRACO-425 for next sprint. Contract tests
  now run in CI so future regressions are caught early.

## Assumptions
- A-DRACO-15-01 — Remaining bug-cluster items are low severity and do not hide a systemic defect.
  (Owner: Rui Santos)

## Issues

### I-DRACO-15-01 — Draco Auth API v2 (DRACO-412) delivery slip — affects Atlas
- **Type:** Issue / Dependency (outbound — Draco is the provider)
- **Owner:** Aisha Khan (Tech Lead)
- **Status:** Open
- **Description:** Draco Auth API v2 (DRACO-412) was originally due end of Sprint 14 (2026-05-15).
  It did not land in Sprint 14 or Sprint 15 and has now **slipped to Sprint 16**. The v2 contract
  freeze took longer than planned.
- **Impact:** Atlas depends on the Draco Auth API v2 surface and will not have it on the originally
  committed date. Their downstream integration work is exposed to this slip.
- **Mitigation:** Aisha to confirm the Sprint 16 delivery date and notify Atlas directly. Tracked on
  DRACO-412 (jira-draco-s15-authapi).

## Dependencies
- D-DRACO-15-01 — Draco Auth API v2 (DRACO-412) consumed by Atlas. Now tracked as the issue above
  (I-DRACO-15-01) given the slip to Sprint 16.
