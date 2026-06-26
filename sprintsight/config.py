"""Minimal .env loader for non-CI runs (no python-dotenv dependency).

The project deliberately has no autoloader; this fills that gap for local and live runs while
keeping CI and real exports authoritative. load_env() reads simple KEY=value lines from a .env
file into os.environ WITHOUT overriding variables already set, and is a no-op when the file is
absent. It never prints values.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | os.PathLike[str] = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")
