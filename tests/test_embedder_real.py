"""Eval (D1): real semantic embedding beats the lexical stand-in.

Property: a query that PARAPHRASES a chunk (shares few/no words but matches its meaning) should
retrieve that chunk. The `HashingEmbedder` stand-in hashes the whole string, so paraphrases land
on near-orthogonal vectors and it cannot do this (the failing baseline that motivates the slice).
A real in-region model can.

CI runs the deterministic baseline (Test A) + the seam contract (Test C) with no model download.
The real-model leg (Test B) is gated: it only runs when `sentence-transformers` is importable AND
`SPRINTSIGHT_EMBEDDER=local`, so it is the by-hand / model-enabled-env live proof, never a CI gate.
"""

import importlib.util
import os

import pytest

from sprintsight.evals.fixtures import Artifact
from sprintsight.ingest.embedding import HashingEmbedder, LocalEmbedder, make_embedder
from sprintsight.retrieval import InMemoryRetriever

# (artifact_id, target chunk text, a paraphrase query that shares few tokens with the target).
PAIRS = [
    (
        "t-auth",
        "The single sign-on login integration with the third-party identity provider is "
        "blocked; we cannot authenticate users until their endpoint is fixed.",
        "users cannot log in because the external identity service is down",
    ),
    (
        "t-db",
        "The database migration for the orders table keeps timing out on the production "
        "replica during the nightly batch window.",
        "the overnight data move on the orders schema is too slow and fails",
    ),
    (
        "t-ui",
        "The checkout page renders a blank white screen on mobile Safari right after the "
        "payment confirmation step.",
        "on iPhones the basket finalisation view shows nothing once you have paid",
    ),
    (
        "t-perf",
        "API response latency spiked above two seconds because the caching layer was "
        "accidentally disabled in the last deployment.",
        "requests got really slow after we shipped, looks like the cache stopped working",
    ),
]


# Unrelated chunks that match none of the queries — they enlarge the candidate pool so the
# lexical stand-in cannot top-rank a target by luck, and the real model must discriminate.
DISTRACTORS = [
    ("d-hire", "We onboarded two new backend engineers and refreshed the team rota this sprint."),
    ("d-docs", "The architecture decision records were migrated into the shared Confluence space."),
    ("d-meet", "The quarterly planning workshop is scheduled for the second week of next month."),
    ("d-budget", "Cloud spend came in under forecast after the reserved-instance purchase."),
]


def _artifacts() -> dict[str, Artifact]:
    rows = [(aid, text) for aid, text, _ in PAIRS] + DISTRACTORS
    return {
        aid: Artifact(
            artifact_id=aid,
            source_type="slack",
            team="Atlas",
            sprint=15,
            meta={"source_ref": aid},
            body=text,
        )
        for aid, text in rows
    }


def _paraphrase_recall(embedder, k: int = 1) -> float:
    """Fraction of paraphrase queries that retrieve their own target chunk in the top-k."""
    retriever = InMemoryRetriever(embedder, artifacts=_artifacts())
    hits = 0
    for aid, _, query in PAIRS:
        res = retriever.search(query, k=k, team="Atlas")
        if any(r.artifact_id == aid for r in res):
            hits += 1
    return hits / len(PAIRS)


def test_lexical_standin_fails_paraphrase_recall():
    # Baseline (always runs in CI): the hashing stand-in lands well below the bar the real model
    # must clear (0.75), because it hashes whole strings and so cannot match paraphrases. This
    # locks the gap the real embedder closes. (Deterministic: hashing is a pure function.)
    assert _paraphrase_recall(HashingEmbedder(), k=1) < 0.75


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is None
    or os.getenv("SPRINTSIGHT_EMBEDDER") != "local",
    reason="real-model leg: needs the [embed] extra and SPRINTSIGHT_EMBEDDER=local (not a CI gate)",
)
def test_real_embedder_clears_paraphrase_recall():
    # Live proof: the real in-region model retrieves the paraphrased target.
    assert _paraphrase_recall(make_embedder(os.environ), k=1) >= 0.75


def test_factory_defaults_to_hashing_standin():
    assert isinstance(make_embedder({}), HashingEmbedder)
    assert isinstance(make_embedder({"SPRINTSIGHT_EMBEDDER": "hashing"}), HashingEmbedder)


def test_factory_selects_local_when_gated_without_loading_model():
    # Selecting the real embedder must NOT import sentence-transformers or load a model (lazy):
    # constructing the object is cheap and dependency-free; the heavy work happens on .embed().
    emb = make_embedder({"SPRINTSIGHT_EMBEDDER": "local"})
    assert isinstance(emb, LocalEmbedder)
    assert emb.dim == 1024
