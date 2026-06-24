"""A1 proof (Stage 7, Goal A): pull live Jira tickets, normalize, ingest, retrieve — and print
real tickets as cited evidence. No web UI.

    # offline, against the recorded sample (default):
    .venv/bin/python scripts/run_connector_demo.py

    # live, against a real board (clean-network day, Composio key set):
    .venv/bin/python scripts/run_connector_demo.py --project SSD

This is the "done" artifact for the slice: it proves the connector pipe end to end.
"""

import argparse
import json
import sys
from pathlib import Path

from sprintsight.connect.connector import Connector, JiraConnector, RecordedConnector
from sprintsight.ingest import ingest_corpus
from sprintsight.ingest.embedding import HashingEmbedder
from sprintsight.ingest.store import InMemoryStore
from sprintsight.retrieval.retriever import InMemoryRetriever

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "jira_sample.json"
DEFAULT_QUERY = "auth api dependency not ready"


def run_demo(connector: Connector, query: str = DEFAULT_QUERY, team: str | None = None) -> dict:
    """Fetch -> ingest -> retrieve. Returns a small machine-readable summary.

    `team` scopes retrieval to one team, so the cited evidence matches the scenario being told
    (the default narrative cites Atlas, which carries the hidden cross-team dependency).
    """
    artifacts = connector.fetch()

    emb = HashingEmbedder()
    store = InMemoryStore()
    report = ingest_corpus(store, emb, artifacts=artifacts)

    retriever = InMemoryRetriever(emb, artifacts=artifacts)
    results = retriever.search(query, k=5, team=team)

    return {
        "artifacts": len(artifacts),
        "ingested": report.ingested,
        "results": len(results),
        "top_source_ref": results[0].source_ref if results else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jira connector A1 proof")
    parser.add_argument("--project", help="live Jira project key (omit for offline recorded mode)")
    parser.add_argument("--recorded", help="path to a captured sample to replay offline")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--team", default="Atlas", help="scope cited evidence to one team")
    args = parser.parse_args(argv)

    if args.project:
        connector: Connector = JiraConnector(args.project)
    elif args.recorded:
        connector = RecordedConnector.from_file(args.recorded)
    else:
        connector = RecordedConnector.from_file(DEFAULT_FIXTURE)
    out = run_demo(connector, query=args.query, team=args.team)
    print("RESULT " + json.dumps(out))
    if out["results"] < 1:
        print("FAIL: connector returned no retrievable evidence")
        return 1
    print(
        f"OK — {out['artifacts']} real tickets ingested; "
        f"top cited ticket {out['top_source_ref']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
