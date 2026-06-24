"""Stage 7 A1 proof: the demo runs end to end offline via RecordedConnector."""

from pathlib import Path

from scripts.run_connector_demo import run_demo
from sprintsight.connect.connector import RecordedConnector

FIXTURE = Path(__file__).parent / "fixtures" / "jira_sample.json"


def test_demo_pulls_ingests_and_retrieves():
    conn = RecordedConnector.from_file(FIXTURE)
    out = run_demo(conn, query="auth api dependency not ready", team="Atlas")
    assert out["artifacts"] == 3
    assert out["ingested"] == 3
    assert out["results"] >= 1
    # Scoped to Atlas, the cited evidence is an Atlas ticket (the watermelon team), not Boreas.
    assert out["top_source_ref"] in {"SSD-12", "SSD-13"}
