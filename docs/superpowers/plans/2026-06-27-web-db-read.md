# Plan — slice 4: web reads evidence FROM the DB

Spec: docs/superpowers/specs/2026-06-27-web-db-read-design.md
Branch: realwiring-web-db-read

Eval-first, all in `sprintsight/web/service.py` + `team.html`, fail-safe and off by default.

1. **Tests first (red)** — `tests/web/test_db_read.py`: gate combos; team-scoping via an injected
   `FakeRetriever` that records its `team` arg; chunk->KnowledgeItem mapping; fail-safe on a
   raising retriever (returns `[]`, still closes); `team_detail` empty-when-off / populated-when-on;
   rendered-page panel present/absent; JSON API carries the field. (13 tests.)

2. **Gate + reader (green)** — `_DB_FLAG`, `_db_enabled()` (flag on AND `DATABASE_URL`),
   `_make_retriever()` seam (lazy `PostgresRetriever`), `db_knowledge_for(team, k)` (team-scoped
   `search`, `make_embedder()`, fail-safe try/except/finally), `_knowledge_item(chunk)` mapper.

3. **View-model + wiring** — `KnowledgeItem` dataclass; `TeamDetail.db_knowledge` field;
   `team_detail()` computes `db_knowledge_for(team)` once and passes it into both the normal and
   the insufficient-evidence returns.

4. **Template + CSS** — a "From the knowledge base (live DB)" panel on `team.html`, rendered only
   when `db_knowledge` is non-empty, placed outside the `has_verdict` branch so it shows for every
   team; `.badge-live` + `.kb-score` styles. JSON API needs no change (`asdict` recurses).

5. **Verify** — full suite, ruff, and the deterministic eval gates (watermelon 4/4, report 4/4,
   cross-tool 7/7) all green; then an independent whole-branch review.

Result: 282 passed (+13) + 4 skipped, ruff clean, all eval gates unchanged.

## Operator step (live, separate)
With the live Supabase loaded (slice 1) and re-ingested with `team_id` (slice 3) and the real
embedder (slice 2), set in the web env: `SPRINTSIGHT_WEB_DB=on`, `DATABASE_URL=<session pooler>`,
`SPRINTSIGHT_EMBEDDER=local` (match ingest), `SPRINTSIGHT_ENV=dev`, log in, open `/team/atlas`, and
confirm the "live DB" panel shows that team's chunks only. (Not a CI step.)
