---
artifact_id: status-cygnus-s14
source_type: confluence
source_ref: CYGNUS-STATUS-S14
title: "Cygnus — Sprint 14 Status Report"
author: "Lena Brandt (Delivery Lead)"
source_timestamp: 2026-05-15T16:30:00Z
team: Cygnus
sprint: 14
---

# Cygnus — Sprint 14 Status

**Overall status: AMBER**

## Summary

We committed 34 points and completed 27. Three stories carry over into Sprint 15.
Velocity for the sprint was 27. We are calling this sprint **amber** rather than green:
delivery held up on the core work, but two issues are dragging us and I want them
visible now rather than after they bite.

## Why amber (the honest read)

1. **Upstream dependency slip.** The Pricing Service v2 endpoint we depend on (owned by the
   Platform team, ticket PLAT-288) did not land on its committed date. Two of our stories
   (CYG-141, CYG-147) sit behind it and could not be completed this sprint. This is the main
   reason for the carry-over.
2. **Resourcing gap.** We have been running a person light. Sofia covered both the checkout
   refactor and the integration tests, which stretched the QA pass thin near the end of the
   sprint. We need a second engineer on the integration work or scope will keep slipping.

Both items are logged in the RAID (raid-cygnus-s14) with owners and mitigations. Nothing here
is hidden — we would rather flag amber early.

## Completed
- CYG-138 Checkout refactor (8 pts)
- CYG-140 Cart validation rules (5 pts)
- CYG-144 Promo-code service (8 pts)
- CYG-149 Session telemetry (6 pts)

## Carried over
- CYG-141 Pricing Service v2 integration (blocked on PLAT-288)
- CYG-147 Pricing display reconciliation (blocked on PLAT-288)
- CYG-150 Integration test backfill (resourcing-constrained)

## Next sprint
Chase PLAT-288 to a firm date; request a second engineer for integration work. Expect to stay
amber until the dependency clears.

— Lena
