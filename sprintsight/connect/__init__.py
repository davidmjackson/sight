"""Stage 7 connectors (Goal A): turn live delivery-tool data into corpus Artifacts.

The Jira-specific, network-touching code lives in `connector.fetch_issues` and emits a stable
simplified issue dict. `normalize` maps that clean dict to the existing `Artifact` shape, so the
rest of the app (ingest, retrieval) is reused unchanged.
"""
