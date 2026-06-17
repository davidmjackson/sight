---
artifact_id: raid-cygnus-s14
source_type: raid
source_ref: CYGNUS-RAID-S14
title: "Cygnus — RAID Log (Sprint 14)"
author: "Lena Brandt (Delivery Lead)"
source_timestamp: 2026-05-15T17:00:00Z
team: Cygnus
sprint: 14
---

# Cygnus RAID — Sprint 14

Reviewed at sprint close 2026-05-15. Status this sprint: amber. The two open risks below are the
reason; both are also called out in the Sprint 14 status report.

## Risks

### R-CYG-14-01 — Upstream Pricing Service v2 dependency slip
- **Type:** Dependency
- **Owner:** Marcus Oyelaran (Tech Lead)
- **Status:** Open
- **Description:** PLAT-288 (Pricing Service v2 endpoint, owned by Platform) missed its committed
  date. CYG-141 and CYG-147 are blocked behind it and have carried over.
- **Impact:** Two stories carried to Sprint 15; integration testing cannot start until the endpoint is live.
- **Mitigation:** Marcus to get a firm delivery date from Platform by 2026-05-19; we stub the
  endpoint contract so our side is ready to integrate the day it lands.

### R-CYG-14-02 — Resourcing gap on integration work
- **Type:** Resource
- **Owner:** Lena Brandt (Delivery Lead)
- **Status:** Open
- **Description:** Team is one engineer short. Sofia is split across the checkout refactor and the
  integration tests, which compressed the QA pass at sprint end.
- **Impact:** Integration test backfill (CYG-150) carried over; quality risk if the split continues.
- **Mitigation:** Lena to request a second engineer for Sprint 15 integration work.

## Assumptions
- A-CYG-14-01 — Platform team still treats PLAT-288 as a committed dependency for us. (Owner: Marcus)

## Issues
- I-CYG-14-01 — None beyond the risks above this sprint.

## Dependencies
- D-CYG-14-01 — Pricing Service v2 (PLAT-288), Platform team. Tracked under R-CYG-14-01.
