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
    assert first.artifacts_total == 36
    assert first.ingested == 36
    assert first.skipped == 0
    assert first.chunks_written >= 36
    counts_after_first = store.counts()
    assert counts_after_first["artifact"] == 36

    # Re-running over the same store changes nothing (content_hash match).
    second = ingest_corpus(store, emb)
    assert second.ingested == 0
    assert second.skipped == 36
    assert second.chunks_written == 0
    assert store.counts() == counts_after_first  # no new rows
