---
artifact_id: slack-atlas-s15-msg-dep
source_type: slack
source_ref: "#atlas-team/p1748275200"
title: "Atlas Slack — Draco auth API dependency heads-up"
author: "Tomás Vidal (Backend Engineer)"
source_timestamp: 2026-05-26T14:20:00Z
team: Atlas
sprint: 15
---

# #atlas-team

**Tomás Vidal** — 15:20
heads up everyone — Draco's auth API v2 (DRACO-412) still isn't ready. I checked their board and it's slipped to Sprint 16. That's the auth integration our account-settings work sits on top of.

**Tomás Vidal** — 15:21
this is going to bite us. half my carry-over is blocked behind their endpoints, I can't finish the secure-settings stories without v2. It was supposed to land end of Sprint 14 and it's now two sprints late.

**Marcus Reed** — 15:24
yeah I saw that. we've been stubbing against the old auth contract but it won't hold once v2 changes the token shape. we're basically building on sand until Draco ships.

**Tomás Vidal** — 15:25
exactly. someone needs to flag this up properly because it's not a "minor item" — it's the reason our burndown's flat.

**Marcus Reed** — 15:27
agreed. will raise with Priya.
