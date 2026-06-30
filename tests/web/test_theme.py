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


PAGES = ["/", "/team/atlas", "/crosstool", "/admin/accounts"]


@pytest.mark.parametrize("path", PAGES)
def test_page_uses_instrument_shell(client, path: str) -> None:
    html = client.get(path).text
    assert 'class="ins"' in html
    assert 'data-app="sprintsight"' in html
    assert 'class="topbar"' in html
    assert 'class="band"' in html
    assert 'main class="page"' in html
    assert "/css/instrument-core.css" in html
    assert "/css/sprintsight.css" in html
    assert "/js/oscilloscope.js" in html


def test_login_uses_instrument_shell(anon_client) -> None:
    html = anon_client.get("/login").text
    assert 'data-app="sprintsight"' in html
    assert "/css/instrument-core.css" in html


def test_login_uses_instrument_card(anon_client) -> None:
    html = anon_client.get("/login").text
    assert "login-card" in html
    assert 'name="csrf_token"' in html  # auth hook preserved
    assert 'name="email"' in html
    assert 'name="password"' in html


def test_reticle_glyph_referenced(client) -> None:
    assert "glyph-sprintsight" in client.get("/").text
