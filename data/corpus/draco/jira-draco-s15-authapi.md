---
artifact_id: jira-draco-s15-authapi
source_type: jira
source_ref: DRACO-412
title: "DRACO-412 — Draco Auth API v2 (delivery slipped to Sprint 16)"
author: "Jira (auto-export)"
source_timestamp: 2026-05-29T17:00:00Z
team: Draco
sprint: 15
---

# DRACO-412 — Draco Auth API v2

| Field | Value |
|-------|-------|
| Key | DRACO-412 |
| Summary | Draco Auth API v2 |
| Type | Story |
| Status | In Progress |
| Assignee | Aisha Khan (Tech Lead) |
| Originally due | 2026-05-15 (end of Sprint 14) |
| Current target | **Sprint 16** |
| Consumer | Atlas team (downstream dependency) |

## Description
Deliver the v2 of the Draco Auth API surface (token introspection, scoped consent, refresh-token
rotation) with a frozen consumer-facing contract. **Atlas depends on this API** for their integration
work.

## Slip history
- **Sprint 14 (orig. due 2026-05-15):** core handlers complete; v2 contract not frozen. Carried over.
- **Sprint 15:** contract freeze took longer than planned (review iterations + the late contract-test
  bug cluster, DRACO-BUGSPIKE-S15). Surface still not consumer-ready. **Slipped to Sprint 16.**

## Comments
**Aisha Khan — 2026-05-28:** Contract is nearly frozen but I'm not shipping it half-baked given Atlas
builds on it. Calling it for Sprint 16. Will give Atlas a firm date at the Sprint 16 planning. Logged
as an issue in our RAID (I-DRACO-15-01).

**Tomás Ferreira — 2026-05-29:** Agreed. This is the main reason for our amber. Flagged to Atlas and
in the status report — we own the slip, no surprises.
