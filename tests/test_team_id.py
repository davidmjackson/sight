"""Slice 3 eval: ingestion populates team rows and artifact.team_id.

The `team` table and `artifact.team_id` exist in the schema but were never populated, so the DB
could not scope by team. This locks the property: after ingestion every artifact is linked to its
team and the five teams exist. Deterministic, no DB (runs against InMemoryStore in CI).
"""

from sprintsight.ingest import ingest_corpus
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.ingest.store import InMemoryStore

CORPUS_TEAMS = {"Atlas", "Boreas", "Cygnus", "Draco", "Echo"}


def test_ingest_creates_the_five_teams():
    store = InMemoryStore()
    ingest_corpus(store, HashingEmbedder())
    assert store.counts()["team"] == len(CORPUS_TEAMS)
    assert set(store.team_keys()) == CORPUS_TEAMS


def test_every_artifact_is_linked_to_a_team():
    store = InMemoryStore()
    ingest_corpus(store, HashingEmbedder())
    rows = list(store.artifacts())
    assert rows, "expected artifacts"
    assert all(r["team_id"] is not None for r in rows)


def test_artifact_team_id_resolves_to_the_correct_team():
    from sprintsight.evals.fixtures import load_corpus

    store = InMemoryStore()
    ingest_corpus(store, HashingEmbedder())

    corpus = load_corpus()
    id_to_key = {tid: key for key, tid in store.team_index().items()}
    # For a sample of artifacts, the stored team_id maps back to the corpus team.
    for art in list(corpus.values())[:5]:
        source_ref = art.meta.get("source_ref", art.artifact_id)
        row = store.artifact(art.source_type, source_ref)
        assert row is not None
        assert id_to_key[row["team_id"]] == art.team


def test_team_upsert_is_idempotent():
    store = InMemoryStore()
    first = store.upsert_team("Atlas", "Atlas")
    second = store.upsert_team("Atlas", "Atlas")
    assert first == second
    assert store.counts()["team"] == 1
