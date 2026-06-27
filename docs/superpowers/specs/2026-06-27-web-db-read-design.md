# Slice 4 — web reads evidence FROM the DB (real-wiring, Epic SS-5)

Plain-English summary (read this first)
---------------------------------------
Today every web screen is computed from the synthetic corpus **files** on disk. This slice makes
the per-team drill-in also show a panel of cited evidence pulled from the **live database** (the
real Supabase we stood up in slice 1), scoped to that one team using the `team_id` link we
populated in slice 3. It is the first time a web page reads real data out of the database.

It is **off by default**. Nothing changes unless an operator sets a flag and a database URL, so
CI, local runs, and the demo all behave exactly as before until you deliberately turn it on. This
is the same fail-safe gate pattern we have now reused five times (LLM writer, crosstool live, auth
dev mode, embedder, and here).

Why only the evidence panel, and not the whole screen
-----------------------------------------------------
The watermelon **detector** is hard-wired to three things that live only in the corpus files: the
semantic id (`status-atlas-s15`), the `sprint` number, and the functional type (`status`,
`burndown`, `triage`...). The database deliberately stores the **generic** shape instead: a
`source_type` enum (`confluence`/`jira`/`slack`/...), a `source_ref` (`ATLAS-STATUS-S15`), the full
body, and `team_id`. It does not store the sprint, the semantic id, or the functional type (the
`sprint`/`sprint_metric`/`burndown_snapshot` tables that would hold sprint are a later slice).

So running the verdict/report off DB rows would need a schema change plus a re-ingest, or brittle
parsing of `source_ref`/body. That is out of scope here. The part that reads **cleanly** from the
DB today is the cited evidence: `PostgresRetriever` is already team-scoped (slice 3's payoff) and
returns the chunks behind each team. This slice surfaces exactly that, and leaves the
corpus-computed verdict + report untouched. (David chose this scope, 2026-06-27.)

In scope
--------
1. A fail-safe gate `_db_enabled()` in `sprintsight/web/service.py`: true only when
   `SPRINTSIGHT_WEB_DB=on` AND `DATABASE_URL` is set. Default off.
2. A DB-backed evidence reader `db_knowledge_for(team)` that queries the live DB through
   `PostgresRetriever`, **team-scoped**, using `make_embedder()` (the same embedder family ingest
   used), and maps the retrieved chunks to a new `KnowledgeItem` view-model. Fail-safe: any error
   (no DB, wrong creds, query failure) logs and returns `[]`, never a 500.
3. A new optional `TeamDetail.db_knowledge: list[KnowledgeItem]` field, populated only when the gate
   is open; empty otherwise (so the page is byte-for-byte unchanged when off).
4. A "From the knowledge base (live)" panel on `team.html`, rendered only when `db_knowledge` is
   non-empty. JSON `GET /api/team/{id}` carries the same field.
5. Eval-first: served-data tests with an **injected fake retriever** so they run fully offline (no
   real DB), proving the gate logic, team-scoping, the chunk->item mapping, and the fail-safe.

Out of scope (named so they are not forgotten)
----------------------------------------------
- Running the verdict/report off DB rows (needs the delivery-domain tables + a schema/re-ingest).
- Portfolio (`/`) reading from the DB — this slice is the team drill-in only.
- A live browser/CI proof of the DB read (operator step, like every prior live-wire slice).
- Connection pooling — the retriever opens and closes one connection per request (fine for the
  single-tenant showcase; flagged as a later optimisation).

Design
------
### Gate (mirrors `_llm_enabled`)
```
_DB_FLAG = "SPRINTSIGHT_WEB_DB"
def _db_enabled() -> bool:
    return os.environ.get(_DB_FLAG) == "on" and bool(os.environ.get("DATABASE_URL"))
```

### Retriever seam (injectable, like `_writer`/`_detector`)
A module-level `_make_retriever` callable builds a real `PostgresRetriever(DATABASE_URL)` by
default; tests monkeypatch it with a fake. `PostgresRetriever` imports psycopg lazily, so the
service module still imports cleanly without the `[db]` extra.

### Reader
```
def db_knowledge_for(team: str, k: int = 5) -> list[KnowledgeItem]:
    if not _db_enabled():
        return []
    query = f"{team} sprint {CURRENT_SPRINT} status risks blockers burndown"
    retriever = None
    try:
        retriever = _make_retriever()
        chunks = retriever.search(query, make_embedder(), k=k, team=team)
        return [_knowledge_item(c) for c in chunks]
    except Exception:
        logging.exception("DB knowledge read failed for team %s", team)
        return []
    finally:
        if retriever is not None:
            retriever.close()
```
`team=team` is the key: it exercises slice 3's `artifact.team_id` scoping so one team's page can
never surface another team's chunks.

### View-model
`KnowledgeItem(source_type, source_ref, snippet, score)` — built from the retrieved chunk's
`source_type`, `source_ref`, `text` (snippet, first line, capped), and `score` (rounded). It does
**not** use `artifact_id`/`sprint`, which `PostgresRetriever` does not populate.

Security
--------
Read-only. No new persisted data, no new external service. The DB credentials already live in the
gitignored `.env` from slice 1. The gate fails closed (off without both the flag and a DSN). The
team filter is the data-isolation control and is the thing the tests pin.

Eval-first
----------
The eval for this UI is the served-data contract (the established "test the served data, not the
pixels" principle), run offline with a fake retriever:
- gate off by default; off with flag but no DSN; off with DSN but no flag; on with both;
- with the gate on + a fake retriever, `team_detail` returns the mapped `KnowledgeItem`s and the
  fake was called with `team=<that team>` (team-scoping);
- a retriever that raises yields `db_knowledge == []` and no exception (fail-safe), and is closed;
- gate off yields `db_knowledge == []` and the page is unchanged;
- HTML smoke: the panel appears when items exist, is absent when empty.
Deterministic watermelon (4/4) + report (4/4) + cross-tool (7/7) eval gates stay the CI gate and
are untouched.
