"""SS-2.6: in-memory retrieval — scoping, provenance, ranking, retrievability."""

from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.retrieval import InMemoryRetriever

VALID_SOURCE_TYPES = {"jira", "confluence", "slack", "raid", "other"}


def _retriever():
    return InMemoryRetriever(HashingEmbedder())


def test_team_scoping_and_provenance():
    res = _retriever().search("sprint status update", k=5, team="Boreas")
    assert res
    assert all(r.team == "Boreas" for r in res)  # scoped to the team
    for r in res:
        assert r.source_type in VALID_SOURCE_TYPES
        assert r.source_ref  # provenance present
        assert r.artifact_id


def test_sprint_scope_and_k_limit():
    res = _retriever().search("anything at all", k=3, team="Atlas", sprints=[15])
    assert len(res) <= 3
    assert all(r.sprint == 15 for r in res)


def test_exact_text_is_top_hit():
    # Mechanism/recall: querying with a chunk's own text returns that chunk first.
    # (Semantic NL recall arrives with the real in-region embedder, D1.)
    retriever = _retriever()
    dep = next(ic for ic in retriever.index if ic.artifact_id == "slack-atlas-s15-msg-dep")
    res = retriever.search(dep.text, k=3, team="Atlas")
    assert res[0].artifact_id == "slack-atlas-s15-msg-dep"
    assert res[0].score > 0.99  # near-identical vector


def test_results_ranked_descending():
    res = _retriever().search("blocker risk dependency", k=5, team="Draco")
    scores = [r.score for r in res]
    assert scores == sorted(scores, reverse=True)
