# Real embedder (decision D1) — runbook

Plain English: by default the app turns text into search vectors with a fake stand-in
(`HashingEmbedder`) that only matches identical words. This runbook turns on the REAL model, which
matches by meaning. The model runs on your own machine (nothing is sent to an outside company), and
it stays OFF unless you set one switch, so the automated tests and offline demos are unaffected.

## The one rule you must not break

Stored chunk vectors and a search query are only comparable if the SAME model made both. So:

> If you change the embedder (or its model id), you MUST re-ingest before you search.

Mixing embedders does not error, it silently returns nonsense. Two safeguards make this hard to get
wrong: the switch below is read by both the ingest step and the search step (so they always agree),
and the ingest dedup hash now includes the embedder identity, so re-ingesting after a switch
re-embeds every artifact instead of skipping it as "unchanged". You do NOT need to clear the table
first. Just confirm the re-ingest actually did work (see step 3).

## Turn it on (synthetic data, against your Supabase)

The model is `thenlper/gte-large` (1024-dim, matches the locked `chunk.embedding vector(1024)`
column). First run downloads it (~1.3 GB) to the local cache; later runs are offline.

1. Install the extra (one off):

---

```bash
.venv/bin/pip install -e '.[embed,db]'
```

---

2. Put the switch + your database URL in `.env` (or export them). The two lines:

```
SPRINTSIGHT_EMBEDDER=local
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

(Optional: `SPRINTSIGHT_EMBED_MODEL=<hf-model-id>` to try a different 1024-dim model.)

3. Re-ingest the synthetic corpus with the real model:

---

```bash
.venv/bin/python scripts/ingest.py
```

---

Check the printed `RESULT {...}` line shows `ingested` greater than 0 (e.g. `ingested: 37`). If it
says `ingested: 0, skipped: 37` the switch did not take effect (the data is still on the old
embedder) and search would be meaningless, so do not proceed until you see a non-zero ingest.

This same re-ingest also backfills `artifact.team_id` (real-wiring slice 3): the team rows are
created and every artifact is linked to its team on this pass, so you get the real vectors and the
team links together. (On a DB that already holds the artifacts, team_id is only set when the
artifact is actually re-ingested, which the embedder switch forces here.)

4. Prove semantic search works on the real DB:

---

```bash
.venv/bin/python scripts/retrieve_smoke.py
```

---

## Prove it the eval way (no DB needed)

With the extra installed and the switch on, the gated eval leg runs the real model and asserts a
paraphrased query retrieves its target chunk (which the stand-in cannot):

---

```bash
SPRINTSIGHT_EMBEDDER=local .venv/bin/python -m pytest tests/test_embedder_real.py -q
```

---

Without the extra / switch, that leg SKIPS and CI stays offline and deterministic.

## What stays on the stand-in (by design)

CI, the LangGraph builder default, and the offline web/connector demos keep `HashingEmbedder` (no
download, fully deterministic). Only the ingest + retrieve scripts honour the switch.
