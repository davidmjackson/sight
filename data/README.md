# Sprintsight — Synthetic Demo Corpus (SS-2.1 / SS-1.3)

Fully synthetic, scenario-first corpus. Four teams × two sprints (Sprint 14, Sprint 15).
No real client data. This is the fixture set every Stage-1 eval and the ingestion pipeline run on.

- **Ground truth** (authored by hand, the IP): `ground-truth/labels.yaml`. One record per team/sprint.
- **Surface artifacts** (generated from the ground truth, then curated): `corpus/<team>/`.

Realises the data strategy in `docs/data/data-strategy.md`. Consumed by the watermelon eval
(`docs/evals/watermelon-eval.md`, SS-1.4) and — later — the report eval (SS-1.5).

## Teams (one line each)

| Team | Reported | Actual | Watermelon? | Role |
|------|----------|--------|-------------|------|
| Atlas | Green, Green | Amber → Red | **YES** | the hero watermelon |
| Boreas | Green, Green | Green | no | true-green precision guard |
| Cygnus | Amber, Amber | Amber | no | honest-amber (reported = actual) |
| Draco | Green, Amber | Amber | no | tricky near-miss (scary signal, under control) |

Cross-team thread: **Atlas depends on Draco's auth API**, which Draco slips. The slip is visible in
Draco's own data and in one Atlas chat message, but absent from Atlas's RAID and status report.

## Sprint calendar

- Sprint 14: 2026-05-04 → 2026-05-15
- Sprint 15: 2026-05-18 → 2026-05-29

## Artifact file format (uniform — ingestion reads this directly in SS-2.5)

One file per artifact, named exactly by its `artifact_id`, under `corpus/<team>/`. Markdown with
YAML frontmatter. Frontmatter maps 1:1 to the `artifact` table in `docs/schema/schema-design.md`.

```markdown
---
artifact_id: status-atlas-s15        # stable id; matches ground truth + eval evidence lists
source_type: confluence              # one of: jira | confluence | slack | raid | other
source_ref: ATLAS-STATUS-S15         # the "native" id in the source system
title: "Atlas — Sprint 15 Status Report"
author: "Priya Nair (Delivery Lead)"
source_timestamp: 2026-05-29T16:00:00Z   # within the sprint window
team: Atlas
sprint: 15
---

<body — believable PM prose / structured content>
```

### source_type mapping

| Artifact kind | source_type | id prefix |
|---------------|-------------|-----------|
| Status report | confluence | `status-<team>-s<NN>` |
| RAID log | raid | `raid-<team>-s<NN>` |
| Ticket / burndown summary | jira | `burndown-<team>-s<NN>` |
| Chat message | slack | `slack-<team>-s<NN>-msg-<key>` |
| Other scenario tickets/notes | jira / confluence | descriptive id |

## Authoring rules (curation pass — data-strategy §8)

- Every seeded signal appears in at least one artifact.
- Every ground-truth label is supported by a citable artifact (its `expected_evidence`).
- Numbers are internally consistent across burndown, velocity, and carry-over (the canonical figures
  live in `labels.yaml` under each record's `metrics`; artifacts must match them).
- Status reports read like real PM prose — never labelled "this is the watermelon".
- Decoy noise (normal chatter, routine tickets) is present so signals are not trivially findable.

## Validation

`labels.yaml` is the source of truth. Every `artifact_id` it lists must exist as a file at
`corpus/<team>/<artifact_id>.md`, and every `expected_evidence` id must resolve to one of those files.
