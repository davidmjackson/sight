---
artifact_id: raid-cygnus-s15
source_type: raid
source_ref: CYGNUS-RAID-S15
title: "Cygnus — RAID Log (Sprint 15)"
author: "Lena Brandt (Delivery Lead)"
source_timestamp: 2026-05-29T17:00:00Z
team: Cygnus
sprint: 15
---

# Cygnus RAID — Sprint 15

Reviewed at sprint close 2026-05-29. Status this sprint: amber. Same two open risks as Sprint 14 —
both still open, both still owned and mitigated, both also named in the Sprint 15 status report. We
report amber because the actual state is amber; nothing here is hidden.

## Risks

### R-CYG-15-01 — Upstream Pricing Service v2 dependency slip (carried from S14)
- **Type:** Dependency
- **Owner:** Marcus Oyelaran (Tech Lead)
- **Status:** Open (escalated)
- **Description:** PLAT-288 (Pricing Service v2 endpoint, owned by Platform) slipped again and is now
  committed to Sprint 16. CYG-141 and CYG-147 remain blocked and have carried over for a second sprint.
- **Impact:** Two stories carried again; integration testing still cannot start. Primary cause of the
  reduced velocity (25).
- **Mitigation:** Marcus has Platform's written Sprint 16 commitment for PLAT-288. Contract stub stays
  in place so we integrate the day it lands. Risk escalated to programme delivery for visibility.

### R-CYG-15-02 — Resourcing gap on integration work (carried from S14)
- **Type:** Resource
- **Owner:** Lena Brandt (Delivery Lead)
- **Status:** Open (escalated)
- **Description:** Still one engineer short. The second engineer requested in Sprint 14 has not been
  allocated. Sofia continues to split across the refactor follow-up and integration tests.
- **Impact:** Integration test backfill (CYG-150) carried over again; sustained quality risk from the
  compressed QA pass.
- **Mitigation:** Lena escalated the staffing request to the programme lead with a hard ask for Sprint 16.
  Interim: Tariq picks up first-pass integration test review to relieve Sofia.

## Assumptions
- A-CYG-15-01 — Platform's Sprint 16 commitment for PLAT-288 holds this time. (Owner: Marcus)

## Issues
- I-CYG-15-01 — None new beyond the two carried risks above.

## Dependencies
- D-CYG-15-01 — Pricing Service v2 (PLAT-288), Platform team. Tracked under R-CYG-15-01.
