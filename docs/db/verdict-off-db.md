# Verdict and report off the live database

Plain summary: a switch that makes the web app compute the watermelon verdict and the report
from the live database instead of the local sample files. Off by default.

## What it needs
1. Migrations applied through `0005_artifact_functional_tags.sql`.
2. A one-time re-ingest of the live database so the new `functional_id` and `sprint` columns
   get filled in (the ingest dedup hash now folds these in, so the first re-ingest rewrites
   every row once; steady state afterwards).
3. Environment: `SPRINTSIGHT_VERDICT_DB=on`, `DATABASE_URL=<session pooler url>`, and the same
   `SPRINTSIGHT_EMBEDDER` you ingested with. For a local run also set `SPRINTSIGHT_ENV=dev`.

## Verify
Log in, open `/team/atlas` and the portfolio. The verdict and report now come from the database.
If the database is unreachable or not yet backfilled, the app silently falls back to the sample
files (fail-safe), so a misconfiguration never 500s; it just looks like today's behaviour.

## Switch off
Unset `SPRINTSIGHT_VERDICT_DB` (or set it to anything other than `on`). Behaviour returns to the
sample files immediately.
