"""Anti-drift guards for the shared risk/dependency vocabulary and the pgvector format.

These two things were duplicated with a subtle divergence between copies (a stray keyword,
and one case-sensitive vs one case-insensitive team match / format). The tests below lock
in that there is now a single source of truth, so a future edit to one caller cannot
silently reintroduce the drift.
"""

from sprintsight import crossteam, detector
from sprintsight.ingest import store
from sprintsight.ingest.embedding import to_pgvector
from sprintsight.retrieval import postgres
from sprintsight.signals import mentions_risk_dependency


def test_detector_and_crossteam_share_one_vocabulary():
    # Both modules must reference the SAME shared helper, not private copies.
    assert detector.mentions_risk_dependency is mentions_risk_dependency
    assert crossteam.mentions_risk_dependency is mentions_risk_dependency
    # The old drift keyword ("late") is gone; neither module keeps a private regex.
    assert not hasattr(crossteam, "_RISK")
    assert not hasattr(crossteam, "_DEP")


def test_mentions_risk_dependency_needs_both_a_risk_and_a_dependency():
    assert mentions_risk_dependency("their auth API isn't ready and it's slipping")
    assert not mentions_risk_dependency("the API shipped on time")  # dependency, no risk
    assert not mentions_risk_dependency("the sprint is blocked")  # risk, no dependency


def test_mentions_risk_dependency_is_case_insensitive():
    assert mentions_risk_dependency("BLOCKED behind their ENDPOINT")


def test_to_pgvector_is_the_single_format_shared_by_writer_and_reader():
    # The writer (store) and reader (postgres) must format vectors identically.
    assert store.to_pgvector is to_pgvector
    assert postgres.to_pgvector is to_pgvector
    assert to_pgvector([0.1, 0.2, -0.3]) == "[0.1,0.2,-0.3]"
