---
artifact_id: status-draco-s15
source_type: confluence
source_ref: DRACO-STATUS-S15
title: "Draco — Sprint 15 Status Report"
author: "Tomás Ferreira (Delivery Lead)"
source_timestamp: 2026-05-29T16:30:00Z
team: Draco
sprint: 15
---

# Draco — Sprint 15 Status

**Overall status: AMBER**

## Summary

We committed 36 points and completed 29. Three stories carry over into Sprint 15's successor.
Velocity for the sprint was 29 — down from 33 last sprint. I'm calling this **amber** honestly,
for two reasons that I want fully visible: a late bug spike, and the Auth API v2 slip.

## Why amber (the honest read)

1. **Late-sprint bug spike — managed, not a fire.** Eighteen bugs were raised against the v2 auth
   surface in the back third of the sprint (tracked as the DRACO-BUGSPIKE-S15 cluster). On its face
   that number looks alarming. We triaged all 18 the same day (see the triage note, triage-draco-s15):
   the large majority are **low/medium severity** — cosmetic, validation-message, and docs-mismatch
   items surfaced by a new contract-test pass. Two mediums are minor and fixed; there are **no
   high/critical** bugs open. Burndown stayed broadly on track through the spike. It cost us a few
   points of velocity, which is the honest reason we're amber rather than green — but it is under
   control, not a hidden red.

2. **Auth API v2 (DRACO-412) has slipped to Sprint 16.** This is the bigger delivery item. The v2
   contract took longer to freeze than planned and the surface will not be ready this sprint either.
   It is now committed for **Sprint 16**. The Atlas team depends on this API, so I have flagged it
   directly — it is logged in our RAID (raid-draco-s15) and on the ticket (jira-draco-s15-authapi).
   We own this slip and are not hiding it.

Both items are in the RAID with owners and mitigations.

## Completed
- DRACO-417 Refresh-token rotation (8 pts)
- DRACO-419 Scoped consent screens (8 pts)
- DRACO-421 Contract-test harness for v2 (5 pts) — this is what surfaced the bug cluster
- DRACO-423 Login telemetry dashboards (8 pts)

## Carried over
- DRACO-412 Draco Auth API v2 (slipped to Sprint 16)
- DRACO-425 Bug-cluster cleanup (remaining low-severity items)
- DRACO-427 v2 docs pass

## Next sprint
Land DRACO-412 in Sprint 16 and give Atlas a firm date; clear the remaining low-severity bugs.

— Tomás
