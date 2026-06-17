---
artifact_id: raid-draco-s14
source_type: raid
source_ref: DRACO-RAID-S14
title: "Draco — RAID Log (Sprint 14)"
author: "Tomás Ferreira (Delivery Lead)"
source_timestamp: 2026-05-15T16:45:00Z
team: Draco
sprint: 14
---

# Draco RAID — Sprint 14

Reviewed at sprint close 2026-05-15. Sprint status: green. Delivery was clean (33 of 36 points,
two low-risk carry-overs). One dependency item is open and owned — flagged below because it affects
another team.

## Risks
- R-DRACO-14-01 — None material this sprint. Burndown tracked to plan; QA pass comfortable.

## Assumptions
- A-DRACO-14-01 — Atlas continues to treat Draco Auth API v2 (DRACO-412) as a committed upstream
  dependency. (Owner: Aisha Khan)

## Issues
- I-DRACO-14-01 — None this sprint.

## Dependencies

### D-DRACO-14-01 — Draco Auth API v2 (DRACO-412), consumed by Atlas
- **Type:** Dependency (outbound — we are the provider)
- **Owner:** Aisha Khan (Tech Lead)
- **Status:** Open
- **Description:** Draco Auth API v2 was targeted for end of Sprint 14 (2026-05-15). Core handlers
  are done but the v2 contract is not yet frozen; the story (DRACO-412) carries into Sprint 15.
- **Impact:** Atlas depends on this surface and will not have it at the originally committed date.
- **Mitigation:** Aisha to freeze the contract early in Sprint 15 and give Atlas a firm date.
  Tracked on DRACO-412.
