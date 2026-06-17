---
artifact_id: bugspike-draco-s15
source_type: jira
source_ref: DRACO-BUGSPIKE-S15
title: "Draco — Bug cluster raised late Sprint 15 (18 bugs)"
author: "Jira (auto-export)"
source_timestamp: 2026-05-27T15:40:00Z
team: Draco
sprint: 15
---

# DRACO-BUGSPIKE-S15 — 18 bugs raised against the v2 auth surface

**Raised:** 2026-05-27 (Sprint 15, day 8 of 10) · **Count:** 18 · **Source:** contract-test harness (DRACO-421)

A single late-sprint run of the new contract-test harness raised **18 bugs** in one afternoon against
the Draco Auth API v2 surface. Raw cluster export below — severity not yet assessed at this point;
this is the unfiltered signal as it landed.

| Bug | Summary | Component |
|-----|---------|-----------|
| DRACO-B-501 | Error body uses `error` not `error_description` | response schema |
| DRACO-B-502 | 401 message wording inconsistent with v1 | response schema |
| DRACO-B-503 | Consent screen copy typo | UI |
| DRACO-B-504 | Docs example shows old scope name | docs |
| DRACO-B-505 | Missing `Retry-After` header on 429 | rate-limit |
| DRACO-B-506 | Timestamp not RFC3339 in audit log | audit |
| DRACO-B-507 | Refresh-token TTL off by 60s vs spec | tokens |
| DRACO-B-508 | Scope list ordering non-deterministic | response schema |
| DRACO-B-509 | Consent screen button label inconsistent | UI |
| DRACO-B-510 | Docs missing the revocation endpoint | docs |
| DRACO-B-511 | 400 returned where 422 expected | response schema |
| DRACO-B-512 | Empty-scope request not rejected cleanly | tokens |
| DRACO-B-513 | Log line missing request id | audit |
| DRACO-B-514 | Pagination cursor not URL-encoded | response schema |
| DRACO-B-515 | Consent screen not keyboard-focusable | UI |
| DRACO-B-516 | Docs scope-table column mislabelled | docs |
| DRACO-B-517 | Header casing inconsistent (`X-Request-Id`) | response schema |
| DRACO-B-518 | Error locale fallback wrong | response schema |

**On its face:** 18 bugs in one afternoon, two days before sprint close, against the headline auth
surface. In isolation this looks like trouble. (Severity triage is recorded separately in
triage-draco-s15.)
