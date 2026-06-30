"""Drift guard: the copied Instrument assets must stay byte-identical to the suite source.

Skips entirely when the suite checkout is absent, so Sprintsight CI stays independent.
"""
import hashlib
from pathlib import Path

import pytest

SUITE = Path("/var/www/suite/shared/theme")
VENDORED = Path(__file__).resolve().parents[2] / "sprintsight" / "web" / "static" / "theme"

# (suite-relative path, vendored-relative path) for each byte-identical copied asset.
PAIRS = [
    ("instrument-core.css", "css/instrument-core.css"),
    ("oscilloscope.js", "js/oscilloscope.js"),
    ("glyphs.svg", "illos/glyphs.svg"),
    ("fonts/bricolage-grotesque-700.woff2", "fonts/bricolage-grotesque-700.woff2"),
    ("fonts/hanken-grotesk-400.woff2", "fonts/hanken-grotesk-400.woff2"),
    ("fonts/hanken-grotesk-500.woff2", "fonts/hanken-grotesk-500.woff2"),
    ("fonts/hanken-grotesk-600.woff2", "fonts/hanken-grotesk-600.woff2"),
    ("fonts/hanken-grotesk-700.woff2", "fonts/hanken-grotesk-700.woff2"),
    ("fonts/ibm-plex-mono-400.woff2", "fonts/ibm-plex-mono-400.woff2"),
    ("fonts/ibm-plex-mono-500.woff2", "fonts/ibm-plex-mono-500.woff2"),
    ("fonts/ibm-plex-mono-600.woff2", "fonts/ibm-plex-mono-600.woff2"),
]

pytestmark = pytest.mark.skipif(
    not SUITE.exists(), reason="suite theme source absent; drift guard skipped"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("suite_rel,vend_rel", PAIRS)
def test_vendored_asset_matches_suite(suite_rel: str, vend_rel: str) -> None:
    dst = VENDORED / vend_rel
    assert dst.exists(), f"vendored asset missing: {vend_rel}"
    assert _sha(dst) == _sha(SUITE / suite_rel), (
        f"{vend_rel} has drifted from the suite source {suite_rel}; re-sync from {SUITE}"
    )
