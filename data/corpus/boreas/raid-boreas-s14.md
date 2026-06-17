---
artifact_id: raid-boreas-s14
source_type: raid
source_ref: BOREAS-RAID-S14
title: "Boreas — RAID Log, Sprint 14"
author: "Lena Ostrom (Scrum Master)"
source_timestamp: 2026-05-14T11:00:00Z
team: Boreas
sprint: 14
---

# Boreas — RAID Log (Sprint 14)

Reviewed in sprint review on 2026-05-14. All items current, owned, and mitigated. No new risks escalated this sprint.

## Risks

| ID | Risk | Likelihood | Impact | Owner | Status | Mitigation |
|----|------|-----------|--------|-------|--------|------------|
| R-B14-01 | QA capacity tight in final week due to overlapping demo prep | Low | Low | Lena Ostrom | Open — mitigated | Demo prep front-loaded to first week; QA confirmed bandwidth for sprint close. Tracking green. |
| R-B14-02 | Notifications service rate-limit unverified at scale | Low | Medium | Tariq Bello | Closed | Load test run 2026-05-12; comfortably within limits. Closed. |

## Assumptions

| ID | Assumption | Owner | Status |
|----|-----------|-------|--------|
| A-B14-01 | Notification copy signed off by product before release | Sofia Reyes | Confirmed 2026-05-11 |

## Issues

| ID | Issue | Owner | Status | Resolution |
|----|-------|-------|--------|-----------|
| I-B14-01 | Flaky integration test in notifications suite | Tariq Bello | Resolved | Root-caused to test timing; stabilised 2026-05-08. |

## Dependencies

| ID | Dependency | On | Owner | Status |
|----|-----------|----|-------|--------|
| D-B14-01 | Shared design-system token update | Platform team | Sofia Reyes | Delivered on time 2026-05-06; no impact. |

*All items reviewed and current. Nothing outstanding requires escalation.*
