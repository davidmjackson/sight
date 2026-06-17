"""Load the synthetic corpus and ground-truth labels (SS-2.1) for eval cases.

The corpus lives at the repo root under `data/` (see data/README.md). These helpers parse
the YAML frontmatter + markdown body artifact format and the ground-truth labels file, so
eval cases can be built from real fixtures without hard-coding paths.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Walk up from this file until the data corpus is found."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "ground-truth" / "labels.yaml").is_file():
            return parent
    raise FileNotFoundError("could not locate repo root (data/ground-truth/labels.yaml missing)")


def data_dir() -> Path:
    return repo_root() / "data"


@dataclass(frozen=True)
class Artifact:
    """One corpus artifact: its frontmatter metadata plus the markdown body."""

    artifact_id: str
    source_type: str
    team: str
    sprint: int
    meta: dict[str, Any]
    body: str


def load_ground_truth() -> dict[str, Any]:
    """Parse data/ground-truth/labels.yaml."""
    path = data_dir() / "ground-truth" / "labels.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_artifact(path: Path) -> Artifact:
    """Parse a single artifact file (YAML frontmatter + markdown body)."""
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"{path} missing YAML frontmatter")
    _, frontmatter, body = raw.split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}
    return Artifact(
        artifact_id=meta.get("artifact_id", path.stem),
        source_type=meta.get("source_type", "other"),
        team=meta.get("team", ""),
        sprint=int(meta.get("sprint", 0)),
        meta=meta,
        body=body.strip(),
    )


def load_corpus() -> dict[str, Artifact]:
    """Load every artifact under data/corpus/, keyed by artifact_id."""
    corpus_dir = data_dir() / "corpus"
    artifacts: dict[str, Artifact] = {}
    for path in sorted(corpus_dir.rglob("*.md")):
        artifact = load_artifact(path)
        artifacts[artifact.artifact_id] = artifact
    return artifacts


def artifacts_for(team: str, sprints: list[int] | None = None) -> dict[str, Artifact]:
    """All artifacts for a team, optionally filtered to specific sprint numbers."""
    return {
        aid: a
        for aid, a in load_corpus().items()
        if a.team.lower() == team.lower() and (sprints is None or a.sprint in sprints)
    }
