---
artifact_id: status-draco-s14
source_type: confluence
source_ref: DRACO-STATUS-S14
title: "Draco — Sprint 14 Status Report"
author: "Tomás Ferreira (Delivery Lead)"
source_timestamp: 2026-05-15T16:00:00Z
team: Draco
sprint: 14
---

# Draco — Sprint 14 Status

**Overall status: GREEN**

## Summary

We committed 36 points and completed 33. Two stories carry over into Sprint 15. Velocity for the
sprint was 33. Burndown tracked close to the ideal line all sprint and we closed clean — this is a
genuine green.

## Completed
- DRACO-401 Token introspection endpoint (8 pts)
- DRACO-404 Session revocation flow (8 pts)
- DRACO-407 Rate-limit middleware (5 pts)
- DRACO-409 Audit-log writer (6 pts)
- DRACO-411 Login telemetry hooks (6 pts)

## Carried over
- DRACO-412 Draco Auth API v2 — contract finalisation (in progress; see note below)
- DRACO-415 Docs pass for the v2 surface (deprioritised, low risk)

## A note on the Auth API v2 (DRACO-412)

DRACO-412 (Auth API v2) was targeted for end of Sprint 14. We got the core handlers done but the
v2 contract is not yet frozen — the consumer-facing schema needs another iteration after review
feedback. It carries into Sprint 15. This is the one item I want flagged: the Atlas team is waiting
on this surface, and it will not be ready at the originally committed date. Logged with Aisha as owner.

Everything else landed. Standups were healthy, no blockers, QA pass was comfortable.

## Next sprint
Freeze the v2 contract and ship DRACO-412; close the docs pass.

— Tomás
