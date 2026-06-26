"""Shared extraction: turn corpus Artifacts into the {key, status, team} ticket dicts the
cross-tool reconciler consumes. Used by both the CLI demo and the web crosstool service.
"""

from sprintsight.evals.fixtures import Artifact


def tickets_from_artifacts(artifacts: dict[str, Artifact]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for art in artifacts.values():
        key = art.meta.get("source_ref", art.artifact_id)
        # status rides in the body's meta line: "**Status:** In Progress · ..."
        status = ""
        for line in art.body.splitlines():
            if "Status:" in line:
                status = line.split("Status:", 1)[1].split("·")[0].strip().strip("*").strip()
                break
        out[key] = {"key": key, "status": status, "team": art.team}
    return out
