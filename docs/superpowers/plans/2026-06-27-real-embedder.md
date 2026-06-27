# Plan: Real embedder (real-wiring slice 2, decision D1)

Date: 2026-06-27
Spec: docs/superpowers/specs/2026-06-27-real-embedder-design.md
Build style: eval-first (red baseline locked in CI, real-model leg gated). Small, single-author
slice with an independent whole-branch review before merge.

## Files

New:
- `tests/test_embedder_real.py` — the new eval + seam-contract tests (write FIRST, must fail/skip
  appropriately before implementation).
- `docs/embedder/real-embedder.md` — runbook (one-command live run + the re-ingest trap).

Edit:
- `sprintsight/ingest/embedding.py` — add `LocalEmbedder` (lazy import) + `make_embedder()` factory.
- `pyproject.toml` — add `[embed]` extra (`sentence-transformers`).
- `scripts/ingest.py` — use `make_embedder()` instead of `HashingEmbedder()` directly.
- `scripts/retrieve_smoke.py` — use `make_embedder()`; keep the same query string.

Untouched (deliberately): the schema (vector(1024) stays), `PostgresStore`, `PostgresRetriever`,
the graph builder + web default (stay on `HashingEmbedder`), and all existing tests.

## Steps (in order)

1. **Eval-first, RED baseline.** Write `tests/test_embedder_real.py`:
   - A small fixture: 3-4 (paraphrase query -> target chunk text) pairs sharing few tokens.
   - A pure helper `semantic_recall(embedder, pairs, k)` that ingests the target chunks into an
     `InMemoryRetriever` and checks the paraphrase query returns the target in top-k.
   - Test A (CI, always runs): `semantic_recall(HashingEmbedder(), ...)` is at/under the low bar
     (proves the gap, the failing baseline). This passes immediately as an assertion-of-the-gap;
     it documents WHY the slice exists and that the harness is wired.
   - Test B (gated): `skipif` unless `sentence-transformers` importable AND
     `SPRINTSIGHT_EMBEDDER=local`; asserts `semantic_recall(make_embedder(), ...)` clears the high
     bar. Skips in CI.
   - Test C (seam contract, no model): `make_embedder()` default is `HashingEmbedder`;
     `SPRINTSIGHT_EMBEDDER=local` returns a `LocalEmbedder`; importing the module without the extra
     does not raise. Run; confirm A + C pass, B skips.

2. **Implement `LocalEmbedder` + `make_embedder()`** in `embedding.py`:
   - `LocalEmbedder(model_id="thenlper/gte-large", dim=1024)`: lazy-imports `sentence_transformers`
     inside `embed()` (friendly ImportError naming the `[embed]` extra if missing); loads the model
     once (cached on the instance); returns L2-normalized 1024-dim float lists. Assert the model's
     output dim == 1024 on first use (fail loud if a mismatched model id is configured).
   - `make_embedder(env=os.environ)`: returns `LocalEmbedder(model id from SPRINTSIGHT_EMBED_MODEL)`
     when `SPRINTSIGHT_EMBEDDER == "local"`, else `HashingEmbedder()`. No network at import time.
   - Re-run step-1 tests: C now passes fully; B still skips without the extra.

3. **Add the `[embed]` extra** to `pyproject.toml` (`sentence-transformers>=3`).

4. **Wire the scripts** to `make_embedder()` (both ingest + retrieve_smoke) and update their
   docstrings to mention the gate + the re-ingest trap. `run_connector_demo.py` stays on the
   stand-in (offline demo).

5. **Full gate:** `ruff check .` clean; full `pytest` green (new A+C pass, B skips, nothing else
   moves); deterministic eval gates unchanged (watermelon 4/4, report 4/4, cross-tool 7/7).

6. **Runbook** `docs/embedder/real-embedder.md`: install `.[embed,db]`, set
   `SPRINTSIGHT_EMBEDDER=local`, re-ingest, run `retrieve_smoke.py`; the loud warning that changing
   the embedder requires a full re-ingest.

7. **Live verification (best effort).** Try to pull `gte-large` and run B + a real
   ingest/retrieve. If the env cannot pull the model, ship built+gated and record the one-command
   live run for David (project-consistent; prior slices shipped this way).

8. **Independent whole-branch review** (separate agent, opus-level) BEFORE merge — never an
   implementer-relayed verdict. Apply blocking findings.

9. **Merge** (`--no-ff`), update HANDOVER.md + memory, add the Jira flag line, push.

## Risk / mitigation

- Wrong-embedder-mismatch garbage retrieval -> single env-driven factory both sides + loud runbook.
- Heavy `sentence-transformers`/`torch` dep -> isolated in `[embed]`, lazy import, never in CI.
- Model id producing != 1024 dims -> assert dim on first use, fail loud.
- Can't pull model in this env -> ship built+gated with runbook (honest, documented).
