from sprintsight.retrieval.db_corpus import rows_to_artifacts


def test_rows_to_artifacts_rebuilds_keyed_dict():
    rows = [
        ("status-atlas-s15", "confluence", "Atlas", 15, "Overall status: green"),
        ("burndown-atlas-s15", "jira", "Atlas", 15, "committed 40 completed 30"),
    ]
    arts = rows_to_artifacts(rows)
    assert set(arts) == {"status-atlas-s15", "burndown-atlas-s15"}
    a = arts["status-atlas-s15"]
    assert a.artifact_id == "status-atlas-s15"
    assert a.source_type == "confluence"
    assert a.team == "Atlas"
    assert a.sprint == 15
    assert a.body == "Overall status: green"
    assert a.meta == {}
