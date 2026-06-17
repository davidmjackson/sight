---
artifact_id: triage-draco-s15
source_type: jira
source_ref: DRACO-TRIAGE-S15
title: "Draco — Triage of the Sprint 15 bug cluster (under control)"
author: "Rui Santos (QA Lead)"
source_timestamp: 2026-05-27T18:20:00Z
team: Draco
sprint: 15
---

# Triage — DRACO-BUGSPIKE-S15 (all 18 bugs)

Triaged same day the cluster landed (2026-05-27). All 18 bugs reviewed and severity-sorted. Headline:
**no high/critical bugs**, the cluster is overwhelmingly low/medium, and it does not threaten the
sprint. This is the evidence that the spike is under control.

## Severity breakdown
| Severity | Count | Notes |
|----------|-------|-------|
| Critical | 0 | none |
| High | 0 | none |
| Medium | 4 | minor, two already fixed in-sprint (B-505, B-507) |
| Low | 14 | cosmetic / docs / wording / schema-tidy |

- **Medium (4):** B-505 (missing `Retry-After`), B-507 (refresh TTL off by 60s) — **fixed**.
  B-511 (400 vs 422), B-512 (empty-scope rejection) — fix in progress, low effort.
- **Low (14):** copy typos, docs mismatches, header-casing, ordering/encoding tidy. Batched into
  DRACO-425 for next sprint. None block any consumer.

## Why this is amber, not red
- The cluster was surfaced by the **new contract-test harness (DRACO-421)** — i.e. this is the test
  suite doing its job on a v2 surface, not production incidents or a quality collapse.
- **Zero high/critical.** The scary number (18) decomposes into cosmetic/docs/wording items.
- **Burndown stayed broadly on track** through the spike (see burndown-draco-s15): the slope kept
  going down; we closed at 7 points remaining, not stalled.
- A risk is logged (R-DRACO-15-01, raid-draco-s15) with owner and mitigation; contract tests now
  run in CI so regressions are caught early.

## Conclusion
The 18-bug spike looks alarming in isolation but is triaged, severity-sorted, and contained. It cost
a few points of velocity (29 vs 33) — which is the honest reason Draco is reporting **amber**. It is
**not** a hidden red and should not read as a watermelon.

— Rui
