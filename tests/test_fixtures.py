"""SS-2.2 + SS-2.1: the harness loads the real corpus and ground truth consistently.

This is the bridge that lets the watermelon eval (SS-2.3) build cases from fixtures.
It also re-checks the corpus integrity asserted when SS-2.1 landed.
"""

from sprintsight.evals.fixtures import load_corpus, load_ground_truth


def test_ground_truth_shape():
    gt = load_ground_truth()
    assert set(gt["sprints"]) == {"14", "15"}
    records = gt["records"]
    assert len(records) == 9  # 4 teams x 2 sprints + Echo s15 (thin-data trap)

    atlas_s15 = next(r for r in records if r["team"] == "Atlas" and r["sprint"] == 15)
    assert atlas_s15["is_watermelon"] is True
    assert atlas_s15["reported_status"] == "green"
    assert atlas_s15["actual_status"] == "red"


def test_corpus_complete():
    corpus = load_corpus()
    assert len(corpus) == 37


def test_every_expected_evidence_resolves():
    corpus = load_corpus()
    for record in load_ground_truth()["records"]:
        for artifact_id in record["expected_evidence"]:
            assert artifact_id in corpus, f"missing evidence artifact {artifact_id}"


def test_risk_in_chat_not_raid_gap():
    # The watermelon's defining gap: the Draco dependency is raised in Atlas chat but is
    # absent from Atlas's RAID and status report.
    corpus = load_corpus()
    assert "DRACO-412" in corpus["slack-atlas-s15-msg-dep"].body
    assert "DRACO-412" not in corpus["raid-atlas-s15"].body
    assert "DRACO-412" not in corpus["status-atlas-s15"].body


def test_echo_is_thin():
    # The fabrication trap: Echo has only a one-line status, no burndown/RAID/chat.
    corpus = load_corpus()
    echo = [aid for aid in corpus if aid.endswith("echo-s15")]
    assert echo == ["status-echo-s15"]
    body = corpus["status-echo-s15"].body
    assert "Committed" not in body and "Velocity" not in body
