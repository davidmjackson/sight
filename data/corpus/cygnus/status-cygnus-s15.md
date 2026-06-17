---
artifact_id: status-cygnus-s15
source_type: confluence
source_ref: CYGNUS-STATUS-S15
title: "Cygnus — Sprint 15 Status Report"
author: "Lena Brandt (Delivery Lead)"
source_timestamp: 2026-05-29T16:30:00Z
team: Cygnus
sprint: 15
---

# Cygnus — Sprint 15 Status

**Overall status: AMBER**

## Summary

We committed 32 points and completed 25. Three stories carry over into Sprint 16. Velocity was 25.
We are reporting **amber** again, and for the same two reasons as last sprint — I want to be straight
about that. Neither has fully cleared.

## Why amber (the honest read)

1. **Dependency slip (still open).** The Pricing Service v2 endpoint, PLAT-288 (Platform team), has
   slipped again — now committed to Sprint 16. CYG-141 and CYG-147 remain blocked behind it and have
   carried over a second time. This is the single biggest drag on our velocity.
2. **Resourcing gap (still open).** We are still one engineer short on integration work. The promised
   second engineer did not arrive this sprint, so Sofia continues to carry both the refactor follow-up
   and the integration tests. The QA pass stays compressed.

Both items are logged, owned, and mitigated in the RAID (raid-cygnus-s15). They are the same slip and
the same resourcing gap we flagged in Sprint 14 — we are not hiding the repeat; we are escalating it.

## Completed
- CYG-152 Checkout refactor follow-up (8 pts)
- CYG-155 Promo-code edge cases (6 pts)
- CYG-158 Session telemetry dashboard (6 pts)
- CYG-160 Cart audit logging (5 pts)

## Carried over
- CYG-141 Pricing Service v2 integration (still blocked on PLAT-288)
- CYG-147 Pricing display reconciliation (still blocked on PLAT-288)
- CYG-150 Integration test backfill (still resourcing-constrained)

## Next sprint
PLAT-288 is now a Sprint 16 commitment from Platform — we will hold them to it and keep the contract
stub ready. Resourcing escalated to the programme level. Expect to remain amber until the dependency
clears and the second engineer lands.

— Lena
