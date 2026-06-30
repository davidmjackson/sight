-- After ingest, every artifact must have a functional_id (verdict-off-DB slice).
-- Exits non-zero via the harness when the count is wrong; see the CI db job.
select
  count(*) filter (where functional_id is null) as null_functional_id,
  count(*) filter (where sprint is null)        as null_sprint
from artifact;
