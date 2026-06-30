import pytest


@pytest.mark.parametrize(
    "asset",
    [
        "/css/instrument-core.css",
        "/js/oscilloscope.js",
        "/illos/glyphs.svg",
        "/illos/sprintsight.svg",
        "/fonts/hanken-grotesk-400.woff2",
    ],
)
def test_theme_assets_served(client, asset: str) -> None:
    assert client.get(asset).status_code == 200
