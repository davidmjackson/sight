"""SS-2.5: chunking offsets, the offline embedder, and idempotent corpus ingestion."""

from sprintsight.ingest import ingest_corpus
from sprintsight.ingest.chunking import chunk_text
from sprintsight.ingest.embedding import EMBEDDING_DIM, HashingEmbedder
from sprintsight.ingest.store import InMemoryStore

SAMPLE = "First paragraph here.\n\nSecond paragraph, a bit longer than the first one.\n\nThird."


def test_chunk_offsets_are_exact():
    chunks = chunk_text(SAMPLE, max_chars=40)
    assert chunks, "expected at least one chunk"
    for i, c in enumerate(chunks):
        assert c.ordinal == i
        assert SAMPLE[c.char_start : c.char_end] == c.text  # offsets reconstruct the text


def test_embedder_dim_and_determinism():
    emb = HashingEmbedder()
    a1, b1 = emb.embed(["alpha", "beta"])
    a2 = emb.embed(["alpha"])[0]
    assert len(a1) == EMBEDDING_DIM
    assert a1 == a2          # deterministic
    assert a1 != b1          # distinct inputs differ


def test_ingest_corpus_is_idempotent():
    store = InMemoryStore()
    emb = HashingEmbedder()

    first = ingest_corpus(store, emb)
    assert first.artifacts_total == 37
    assert first.ingested == 37
    assert first.skipped == 0
    assert first.chunks_written >= 37
    counts_after_first = store.counts()
    assert counts_after_first["artifact"] == 37

    # Re-running over the same store changes nothing (content_hash match).
    second = ingest_corpus(store, emb)
    assert second.ingested == 0
    assert second.skipped == 37
    assert second.chunks_written == 0
    assert store.counts() == counts_after_first  # no new rows


def test_ingest_persists_functional_id_and_sprint():
    from sprintsight.evals.fixtures import Artifact
    from sprintsight.ingest.embedding import HashingEmbedder
    from sprintsight.ingest.pipeline import ingest_corpus
    from sprintsight.ingest.store import InMemoryStore

    arts = {
        "status-atlas-s15": Artifact(
            artifact_id="status-atlas-s15", source_type="confluence", team="Atlas",
            sprint=15, meta={"source_ref": "ATLAS-STATUS-S15"}, body="Overall status: green",
        ),
    }
    store = InMemoryStore()
    ingest_corpus(store, HashingEmbedder(), artifacts=arts)

    row = store.artifact("confluence", "ATLAS-STATUS-S15")
    assert row is not None
    assert row["functional_id"] == "status-atlas-s15"
    assert row["sprint"] == 15


def test_reingest_backfills_after_hash_format_change():
    # A store populated under the OLD hash (body+embedder only) must NOT be skipped once the hash
    # folds in functional_id/sprint; it re-ingests so the new columns get populated.
    import hashlib

    from sprintsight.evals.fixtures import Artifact
    from sprintsight.ingest.embedding import HashingEmbedder, embedder_signature
    from sprintsight.ingest.pipeline import ingest_corpus
    from sprintsight.ingest.store import ArtifactInput, InMemoryStore

    art = Artifact(
        artifact_id="status-atlas-s15", source_type="confluence", team="Atlas", sprint=15,
        meta={"source_ref": "ATLAS-STATUS-S15"}, body="Overall status: green",
    )
    sig = embedder_signature(HashingEmbedder())
    old_hash = hashlib.sha256(f"{sig}\n{art.body}".encode()).hexdigest()  # OLD format
    store = InMemoryStore()
    store.upsert_team("Atlas", "Atlas")
    store.upsert_artifact(ArtifactInput(
        source_type="confluence", source_ref="ATLAS-STATUS-S15", title=None, body=art.body,
        author=None, source_timestamp=None, content_hash=old_hash, team_id="t1",
    ))

    report = ingest_corpus(store, HashingEmbedder(), artifacts={art.artifact_id: art})
    assert report.ingested == 1  # NOT skipped
    assert store.artifact("confluence", "ATLAS-STATUS-S15")["functional_id"] == "status-atlas-s15"


class _OtherEmbedder:
    """A distinct 1024-dim embedder (different signature) for the re-embed test."""

    dim = 1024
    model_id = "other-test-model"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]


def test_changing_embedder_forces_reembed_not_skip():
    # The dedup hash includes the embedder signature, so switching embedders against an already
    # populated store re-embeds every artifact (it must NOT silently skip and keep stale vectors).
    store = InMemoryStore()
    ingest_corpus(store, HashingEmbedder())

    switched = ingest_corpus(store, _OtherEmbedder())
    assert switched.skipped == 0
    assert switched.ingested == 37
    assert switched.chunks_written >= 37

    # Idempotent again under the new embedder.
    again = ingest_corpus(store, _OtherEmbedder())
    assert again.ingested == 0
    assert again.skipped == 37
