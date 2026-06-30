# Suite Design Alignment (Instrument) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin all five Sprintsight web pages onto the shared Sprint Suite "Instrument" design system (faithful-copied assets + an indigo accent + a reticle glyph), changing only markup, classes, and static assets.

**Architecture:** Vendor the Instrument theme files byte-identically into `sprintsight/web/static/theme/` and serve them at the web-root URLs Instrument's absolute `url()`/`href`s expect (`/css`, `/js`, `/illos`, `/fonts`). Rebuild `base.html` as the Instrument shell (topbar + scope-trace band + page + footer) and add a Sprintsight per-app stylesheet (`sprintsight.css`) that sets the indigo accent and a *separate* red/amber/green watermelon verdict set, then reskin each content template onto Instrument components. A SHA-256 drift-guard test flags any divergence of the copied files from the suite source and skips when that source is absent.

**Tech Stack:** Python 3, FastAPI, Starlette `StaticFiles`, Jinja2, pytest. CSS is `oklch()` tokens; one vanilla ES-module animation (`oscilloscope.js`). No build step, no new dependency.

## Global Constraints

- **Eval-first.** Web tests assert *served markup*, not pixels. Write/adjust the test before the template change; deterministic eval gates (watermelon 4/4, report 4/4, cross-tool 7/7) must stay unchanged.
- **No logic changes.** No edits to detector, report writer, services (`service.py`, `crosstool_service.py`), auth, or evals. Markup/classes/static assets only.
- **Copied suite assets are byte-identical.** `instrument-core.css`, `oscilloscope.js`, `glyphs.svg`, and the 8 `.woff2` fonts are copied verbatim from `/var/www/suite/shared/theme/` and are drift-checked. `sprintsight.css` and `sprintsight.svg` are OURS and are NOT drift-checked.
- **Assets must serve at web-root paths.** Instrument's `@font-face` uses `url("/fonts/...")` and brand marks use `href="/illos/...svg#..."`; the copied files only work if served at `/css`, `/js`, `/illos`, `/fonts`.
- **Indigo accent, separate verdict set.** Accent hue is indigo (~262); the red/amber/green watermelon colours are their own token set and the accent never uses them.
- **Preserve auth-test hooks.** The login form MUST keep the hidden `csrf_token` field (matched by `tests/web/conftest.py` regex `name="csrf_token" value="..."`), `name="email"`, `name="password"`, and render the error string (test_auth_flow checks `"invalid"` in the error text).
- **No inline styles/scripts** (stay CSP-clean): all CSS in stylesheets, the only `<script>` is the external module `/js/oscilloscope.js`.
- **No em dashes** in any prose a human reads (HANDOVER flag line).
- After every task: `ruff check .` clean and the task's tests green.

## File Structure

Created:
- `sprintsight/web/static/theme/css/instrument-core.css` (copied, drift-checked)
- `sprintsight/web/static/theme/css/sprintsight.css` (ours)
- `sprintsight/web/static/theme/js/oscilloscope.js` (copied, drift-checked)
- `sprintsight/web/static/theme/illos/glyphs.svg` (copied, drift-checked)
- `sprintsight/web/static/theme/illos/sprintsight.svg` (ours — the reticle)
- `sprintsight/web/static/theme/fonts/*.woff2` (8 files, copied, drift-checked)
- `tests/web/test_theme_drift.py` (drift guard)
- `tests/web/test_theme.py` (shell + asset-serve assertions)

Modified:
- `sprintsight/web/app.py` (swap `/static` mount for `/css`, `/js`, `/illos`, `/fonts`)
- `sprintsight/web/templates/base.html` (Instrument shell)
- `sprintsight/web/templates/{login,portfolio,team,crosstool,admin_accounts}.html` (reskin)
- `tests/web/test_pages.py` (update three shell-class assertions)

Deleted:
- `sprintsight/web/static/app.css` (superseded)

---

### Task 1: Vendor the Instrument assets, the reticle glyph, web-root mounts, and the drift guard

**Files:**
- Create: `sprintsight/web/static/theme/{css,js,illos,fonts}/...` (copied suite assets)
- Create: `sprintsight/web/static/theme/illos/sprintsight.svg` (the reticle)
- Modify: `sprintsight/web/app.py:26-39` (mount the four web-root dirs alongside the existing `/static` mount)
- Test: `tests/web/test_theme_drift.py`, plus an asset-serve smoke test added to `tests/web/test_theme.py`

**Interfaces:**
- Consumes: nothing.
- Produces: assets served at `/css/instrument-core.css`, `/js/oscilloscope.js`, `/illos/glyphs.svg`, `/illos/sprintsight.svg`, `/fonts/<name>.woff2`. The reticle symbol id is `glyph-sprintsight`. (`/css/sprintsight.css` is added in Task 2.)

- [ ] **Step 1: Copy the suite theme files into the vendored layout**

Run (one command):

```bash
cd /var/www/sight && mkdir -p sprintsight/web/static/theme/css sprintsight/web/static/theme/js sprintsight/web/static/theme/illos sprintsight/web/static/theme/fonts && cp /var/www/suite/shared/theme/instrument-core.css sprintsight/web/static/theme/css/ && cp /var/www/suite/shared/theme/oscilloscope.js sprintsight/web/static/theme/js/ && cp /var/www/suite/shared/theme/glyphs.svg sprintsight/web/static/theme/illos/ && cp /var/www/suite/shared/theme/fonts/*.woff2 sprintsight/web/static/theme/fonts/
```

Expected: 8 fonts plus the three root assets copied. Verify with `ls sprintsight/web/static/theme/fonts | wc -l` -> `8`.

- [ ] **Step 2: Author the reticle glyph**

Create `sprintsight/web/static/theme/illos/sprintsight.svg` (ours; matches the suite glyph style — `viewBox="0 0 24 24"`, `currentColor`, stroke-width 2):

```svg
<svg xmlns="http://www.w3.org/2000/svg" style="display:none">
  <symbol id="glyph-sprintsight" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
    <circle cx="12" cy="12" r="8.5" opacity="0.55"/>
    <path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4"/>
    <circle cx="12" cy="12" r="2" fill="currentColor" stroke="none"/>
  </symbol>
</svg>
```

- [ ] **Step 3: Write the failing drift-guard test**

Create `tests/web/test_theme_drift.py`:

```python
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
```

- [ ] **Step 4: Run the drift test to verify it passes (assets already copied)**

Run: `.venv/bin/pytest tests/web/test_theme_drift.py -q`
Expected: PASS (11 parametrized cases) — proves the copies are byte-identical. (If the suite source path is absent in this environment, it SKIPS; that is the intended fallback.)

- [ ] **Step 5: Add the web-root mounts in `app.py`**

In `sprintsight/web/app.py`, after `_TEMPLATES = ...` (line 27) add the theme dir constant:

```python
_THEME = _HERE / "static" / "theme"
```

Then replace the single static mount (currently `app.mount("/static", ...)` at line 39) with the four web-root mounts (keep `/static` too so nothing else breaks mid-migration; it is removed in Task 2):

```python
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")
    app.mount("/css", StaticFiles(directory=str(_THEME / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(_THEME / "js")), name="js")
    app.mount("/illos", StaticFiles(directory=str(_THEME / "illos")), name="illos")
    app.mount("/fonts", StaticFiles(directory=str(_THEME / "fonts")), name="fonts")
```

- [ ] **Step 6: Write the failing asset-serve smoke test**

Create `tests/web/test_theme.py` (the shell assertions are added in Task 2; this file starts with the serve check):

```python
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
```

- [ ] **Step 7: Run the asset-serve test**

Run: `.venv/bin/pytest tests/web/test_theme.py -q`
Expected: PASS (5 cases) — the mounts serve every copied asset and the reticle.

- [ ] **Step 8: Commit**

```bash
git add sprintsight/web/static/theme sprintsight/web/app.py tests/web/test_theme_drift.py tests/web/test_theme.py
git commit -m "feat(web): vendor Instrument theme assets + web-root mounts + drift guard"
```

---

### Task 2: Instrument page shell + Sprintsight stylesheet + theme tests

**Files:**
- Create: `sprintsight/web/static/theme/css/sprintsight.css`
- Modify: `sprintsight/web/templates/base.html` (full rebuild)
- Modify: `sprintsight/web/app.py` (remove the `/static` mount)
- Modify: `tests/web/test_pages.py` (three shell-class assertions), `tests/web/test_theme.py` (add shell assertions)
- Delete: `sprintsight/web/static/app.css`

**Interfaces:**
- Consumes: the assets + mounts from Task 1.
- Produces: every page (all extend `base.html`) renders `<body class="ins" data-app="sprintsight">` with `.topbar`, `.band` (with a `.waves` mount), `<main class="page">`, `.footer`, and head links `/css/instrument-core.css` then `/css/sprintsight.css` and the module `/js/oscilloscope.js`. New Jinja blocks for content pages: `{% block eyebrow %}`, `{% block heading %}`, `{% block sub %}`, `{% block main %}`. Sprintsight component classes (`summary-band`, `kpi`, `rag`, `rag-{green,amber,red,unknown}`, `badge`, `badge-{watermelon,ok,muted,stalled,live}`, `verdict-banner`, `verdict-emoji`, `audience-tabs`, `audience-switch`, `aud`, `aud-active`, `evidence-card`, `report-body`, `sources-list`, `login-card`, `login-form`, `error`) are all defined in `sprintsight.css`.

- [ ] **Step 1: Author `sprintsight.css`**

Create `sprintsight/web/static/theme/css/sprintsight.css`:

```css
/* Sprintsight per-app stylesheet — layers on instrument-core.css.
   Indigo accent + a SEPARATE red/amber/green verdict set for the watermelon. */
.ins[data-app="sprintsight"]{
  /* indigo accent (the unused hue between Retro teal and Plan violet) */
  --accent:oklch(0.50 0.10 262);
  --accent-deep:oklch(0.42 0.10 262);
  --accent-wash:oklch(0.95 0.03 262);
  /* radius / shadow (suite values) */
  --r-1:7px; --r-2:10px;
  --shadow-1:0 1px 2px oklch(0.3 0.05 240 / 0.06);
  /* watermelon verdict set — DELIBERATELY separate from the accent */
  --rag-red:oklch(0.55 0.19 25);    --rag-red-wash:oklch(0.95 0.04 25);
  --rag-amber:oklch(0.70 0.13 70);  --rag-amber-wash:oklch(0.95 0.05 78);
  --rag-green:oklch(0.55 0.12 150); --rag-green-wash:oklch(0.95 0.04 150);
  --rag-unknown:oklch(0.62 0.01 250);
}

/* accent overrides for instrument primitives that hardcode --green */
.ins[data-app="sprintsight"] .brand .mk{color:var(--accent);}
.ins[data-app="sprintsight"] .waves{color:var(--accent);}
.ins[data-app="sprintsight"] .btn-pri{background:var(--accent); color:#fff;}
.ins[data-app="sprintsight"] .input:focus{border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-wash);}
.ins[data-app="sprintsight"] a.lnk{color:var(--accent); border-bottom-color:color-mix(in oklab,var(--accent) 30%,transparent);}

/* summary band */
.ins .summary-band{display:flex; gap:12px; flex-wrap:wrap;}
.ins .kpi{flex:1 1 150px; background:var(--panel); border:1px solid var(--line2); border-radius:var(--r-2); padding:16px 18px;}
.ins .kpi .num{font-family:'Bricolage Grotesque',sans-serif; font-size:26px; font-weight:700; letter-spacing:-0.02em; display:block;}
.ins .kpi .label{font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:0.12em; text-transform:uppercase; color:var(--faint); font-weight:500; display:block; margin-top:4px;}
.ins .kpi-alert .num{color:var(--rag-red);}

/* portfolio + cross-tool tables */
.ins table.portfolio td a{color:var(--ink); font-weight:600; text-decoration:none;}
.ins table.portfolio td a:hover{color:var(--accent);}
.ins tr.watermelon{background:var(--rag-red-wash);}
.ins td.evidence{font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--soft);}

/* RAG chips */
.ins .rag{font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; padding:3px 9px; border-radius:5px; color:#fff; text-transform:capitalize; display:inline-block;}
.ins .rag-green{background:var(--rag-green);}
.ins .rag-amber{background:var(--rag-amber);}
.ins .rag-red{background:var(--rag-red);}
.ins .rag-unknown{background:var(--rag-unknown);}

/* flag badges */
.ins .badge{font-family:'IBM Plex Mono',monospace; font-size:10.5px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; padding:4px 9px; border-radius:5px; display:inline-flex; align-items:center;}
.ins .badge-watermelon{background:var(--rag-red-wash); color:var(--rag-red);}
.ins .badge-ok{background:var(--greenwash); color:var(--green);}
.ins .badge-muted{background:oklch(0.93 0.006 250); color:var(--faint);}
.ins .badge-stalled{background:var(--rag-amber-wash); color:oklch(0.5 0.12 60);}
.ins .badge-live{background:var(--accent-wash); color:var(--accent-deep);}
.ins .kb-score{font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--faint); margin-left:8px;}

/* team drill-in */
.ins .verdict-banner{display:flex; gap:14px; align-items:center; background:var(--rag-red-wash); border-color:color-mix(in oklab,var(--rag-red) 30%,var(--line2));}
.ins .verdict-emoji{font-size:30px; line-height:1;}
.ins .verdict-banner h2{margin:0;}
.ins .verdict-banner .sub{margin-top:4px; color:var(--soft); font-size:14px;}
.ins .detail h2{font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:0.12em; text-transform:uppercase; color:var(--faint); font-weight:600; margin:18px 0 8px;}
.ins .detail h2:first-child{margin-top:0;}
.ins .explanation{margin:0;}
.ins ul.signals{margin:6px 0; padding-left:18px;}
.ins ul.signals li{margin:4px 0;}
.ins ul.evidence{list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:8px;}
.ins .evidence-card{border:1px solid var(--line2); border-radius:var(--r-1); padding:10px 12px; background:var(--bone);}
.ins .snippet{color:var(--soft); font-size:13px; margin-top:4px;}
.ins code{font-family:'IBM Plex Mono',monospace; font-size:12px; background:var(--bone); border:1px solid var(--line); color:var(--soft); padding:1px 6px; border-radius:4px;}

/* audience tabs */
.ins .audience-tabs{display:inline-flex; gap:4px; background:var(--bone); border:1px solid var(--line2); padding:4px; border-radius:var(--r-1); margin:6px 0 14px;}
.ins .audience-switch .aud{display:inline-block; padding:6px 14px; border-radius:5px; font-size:13px; font-weight:600; color:var(--soft); text-decoration:none;}
.ins .audience-switch .aud-active{background:var(--panel); color:var(--ink); box-shadow:var(--shadow-1);}
.ins .report-body{white-space:pre-wrap; margin:0 0 8px; color:var(--ink);}
.ins .detail h3, .ins .card h3{font-size:14px; margin:14px 0 4px;}
.ins .sources-list{border-top:1px solid var(--line); margin-top:16px; padding-top:12px;}
.ins ul.sources{list-style:none; padding:0; margin:0; color:var(--soft); font-size:13px;}
.ins ul.sources li{margin:4px 0;}

/* login */
.ins .login-card{max-width:24rem; margin:0 auto;}
.ins .login-form{display:flex; flex-direction:column; gap:14px;}
.ins .error{color:var(--rag-red); font-size:13px;}
```

- [ ] **Step 2: Rebuild `base.html` as the Instrument shell**

Replace the whole of `sprintsight/web/templates/base.html` with:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Sprintsight{% endblock %}</title>
  <link rel="stylesheet" href="/css/instrument-core.css">
  <link rel="stylesheet" href="/css/sprintsight.css">
  <script type="module" src="/js/oscilloscope.js"></script>
</head>
<body class="ins" data-app="sprintsight">
  <header class="topbar">
    <a href="/" class="brand"><span class="mk"><svg width="22" height="22"><use href="/illos/sprintsight.svg#glyph-sprintsight"/></svg></span>Sprintsight</a>
    <span class="tbacts">
      {% if user %}
        <span class="micro">{{ user.email }} &middot; {{ user.role }}</span>
        <a class="btn btn-ghost btn-sm" href="/logout">Sign out</a>
      {% else %}
        <a class="btn btn-ghost btn-sm" href="/login">Sign in</a>
      {% endif %}
    </span>
  </header>
  <div class="band">
    <div class="waves" aria-hidden="true"></div>
    <div class="band-in">
      <p class="eyebrow">{% block eyebrow %}Watermelon detector{% endblock %}</p>
      <h1>{% block heading %}Sprintsight{% endblock %}</h1>
      <p class="sub">{% block sub %}{% endblock %}</p>
    </div>
  </div>
  <main class="page">{% block main %}{% endblock %}</main>
  <footer class="footer">Sprintsight &middot; Sprint Suite</footer>
</body>
</html>
```

- [ ] **Step 3: Remove the superseded `/static` mount and delete `app.css`**

In `sprintsight/web/app.py`, delete the line:

```python
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")
```

Then delete the old stylesheet:

```bash
git rm sprintsight/web/static/app.css
```

- [ ] **Step 4: Add the shell assertions to `tests/web/test_theme.py`**

Append to `tests/web/test_theme.py`:

```python
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


def test_reticle_glyph_referenced(client) -> None:
    assert "glyph-sprintsight" in client.get("/").text
```

- [ ] **Step 5: Update the three old shell-class assertions in `tests/web/test_pages.py`**

Edit `tests/web/test_pages.py`:

`test_shell_has_branded_header` (lines ~42-45) becomes:

```python
def test_shell_has_branded_header(client):
    html = client.get("/").text
    assert 'data-app="sprintsight"' in html
    assert "glyph-sprintsight" in html
```

`test_login_page_uses_shell` (lines ~67-70) becomes:

```python
def test_login_page_uses_shell(anon_client):
    html = anon_client.get("/login").text
    assert 'data-app="sprintsight"' in html  # inherits the Instrument shell
    assert "glyph-sprintsight" in html
```

`test_admin_accounts_uses_shell` (lines ~73-76) becomes:

```python
def test_admin_accounts_uses_shell(client):
    html = client.get("/admin/accounts").text
    assert 'data-app="sprintsight"' in html
    assert "Accounts" in html
```

- [ ] **Step 6: Run the theme + pages tests**

Run: `.venv/bin/pytest tests/web/test_theme.py tests/web/test_pages.py -q`
Expected: PASS. The shell tests pass because every content template extends the rebuilt `base.html`; the three updated assertions match the new shell. The summary-band / verdict-banner / audience-tabs assertions still pass (those classes are defined in `sprintsight.css` and the content templates are reskinned in later tasks but keep the class names).

- [ ] **Step 7: Run the full web suite to confirm no regression**

Run: `.venv/bin/pytest tests/web -q && .venv/bin/ruff check .`
Expected: PASS, ruff clean. (Content pages may show a transient duplicate heading until reskinned in Tasks 3-7; this is cosmetic and not asserted.)

- [ ] **Step 8: Commit**

```bash
git add sprintsight/web/static/theme/css/sprintsight.css sprintsight/web/templates/base.html sprintsight/web/app.py tests/web/test_theme.py tests/web/test_pages.py
git rm sprintsight/web/static/app.css
git commit -m "feat(web): Instrument shell + sprintsight.css; retire app.css"
```

---

### Task 3: Reskin `login.html`

**Files:**
- Modify: `sprintsight/web/templates/login.html`
- Test: `tests/web/test_theme.py` (add a login-card assertion)

**Interfaces:**
- Consumes: the shell blocks (`eyebrow`/`heading`/`sub`/`main`) and `.card`/`.field`/`.input`/`.btn-pri`/`.login-card` from `sprintsight.css`.
- Produces: a login page whose form preserves `name="email"`, `name="password"`, the hidden `csrf_token` field, and the `error` string.

- [ ] **Step 1: Add the failing assertion**

Append to `tests/web/test_theme.py`:

```python
def test_login_uses_instrument_card(anon_client) -> None:
    html = anon_client.get("/login").text
    assert "login-card" in html
    assert 'name="csrf_token"' in html  # auth hook preserved
    assert 'name="email"' in html
    assert 'name="password"' in html
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/web/test_theme.py::test_login_uses_instrument_card -q`
Expected: FAIL on `assert "login-card" in html` (old markup uses `class="login"`).

- [ ] **Step 3: Reskin the template**

Replace the whole of `sprintsight/web/templates/login.html` with:

```html
{% extends "base.html" %}
{% block title %}Sign in - Sprintsight{% endblock %}
{% block eyebrow %}Account{% endblock %}
{% block heading %}Sign in{% endblock %}
{% block sub %}Sign in to view the team portfolio.{% endblock %}
{% block main %}
<div class="card login-card">
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post" action="/login" class="login-form">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <div class="field">
      <label class="label" for="email">Email</label>
      <input class="input" id="email" type="email" name="email" autocomplete="username" required>
    </div>
    <div class="field">
      <label class="label" for="password">Password</label>
      <input class="input" id="password" type="password" name="password" autocomplete="current-password" required>
    </div>
    <button class="btn btn-pri" type="submit">Sign in</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 4: Run the login + auth-flow tests**

Run: `.venv/bin/pytest tests/web/test_theme.py::test_login_uses_instrument_card tests/web/test_auth_flow.py -q`
Expected: PASS (the new assertion and all auth-flow tests, since the form hooks are preserved).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/templates/login.html tests/web/test_theme.py
git commit -m "feat(web): reskin login onto Instrument card"
```

---

### Task 4: Reskin `portfolio.html`

**Files:**
- Modify: `sprintsight/web/templates/portfolio.html`
- Test: `tests/web/test_pages.py` (add a card assertion to an existing portfolio test)

**Interfaces:**
- Consumes: shell blocks; `.summary-band`/`.kpi`, `.card`, `.table-wrap`/`table.table`, `.rag`/`.badge`, `.lnk`.
- Produces: portfolio page; preserves team names, the `/crosstool` link, the word `watermelon`, `summary-band`, and the KPI labels (`Watermelons flagged`, `Teams tracked`).

- [ ] **Step 1: Add the failing assertion**

In `tests/web/test_pages.py`, extend `test_portfolio_page_shows_summary_band`:

```python
def test_portfolio_page_shows_summary_band(client):
    html = client.get("/").text
    assert "summary-band" in html
    assert "Watermelon" in html  # KPI label
    assert "Teams tracked" in html
    assert 'class="card"' in html  # table now lives in an Instrument card
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/web/test_pages.py::test_portfolio_page_shows_summary_band -q`
Expected: FAIL on `'class="card"'` (old portfolio has no card).

- [ ] **Step 3: Reskin the template**

Replace the whole of `sprintsight/web/templates/portfolio.html` with:

```html
{% extends "base.html" %}
{% block title %}Portfolio{% endblock %}
{% block eyebrow %}Portfolio{% endblock %}
{% block heading %}Team portfolio{% endblock %}
{% block sub %}Reported status versus what the data actually shows, as of Sprint {{ summary.sprint }}.{% endblock %}
{% block main %}
<div class="summary-band">
  <div class="kpi{% if summary.watermelons %} kpi-alert{% endif %}">
    <span class="num">{{ summary.watermelons }}</span><span class="label">Watermelons flagged</span>
  </div>
  <div class="kpi"><span class="num">{{ summary.teams_tracked }}</span><span class="label">Teams tracked</span></div>
  <div class="kpi"><span class="num">{{ summary.insufficient }}</span><span class="label">Insufficient evidence</span></div>
  <div class="kpi"><span class="num">{{ summary.sprint }}</span><span class="label">Current sprint</span></div>
</div>

<div class="card">
  <p class="lede">Cross-tool signals: <a class="lnk" href="/crosstool">Jira vs GitHub</a>.</p>
  <div class="table-wrap">
    <table class="table portfolio">
      <thead><tr><th>Team</th><th>Reported</th><th>Actual</th><th>Flag</th></tr></thead>
      <tbody>
      {% for row in rows %}
        <tr class="{{ 'watermelon' if row.is_watermelon else '' }}">
          <td><a class="lnk" href="/team/{{ row.team|lower }}">{{ row.team }}</a></td>
          <td><span class="rag rag-{{ row.reported_status }}">{{ row.reported_status }}</span></td>
          <td><span class="rag rag-{{ row.actual_status }}">{{ row.actual_status }}</span></td>
          <td>
            {% if not row.has_verdict %}<span class="badge badge-muted">insufficient evidence</span>
            {% elif row.is_watermelon %}<span class="badge badge-watermelon" title="Reported healthier than reality">watermelon</span>
            {% else %}<span class="badge badge-ok">consistent</span>{% endif %}
          </td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Run the portfolio tests**

Run: `.venv/bin/pytest tests/web/test_pages.py -k portfolio -q`
Expected: PASS (team listing, Atlas flag, summary band + card, crosstool link).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/templates/portfolio.html tests/web/test_pages.py
git commit -m "feat(web): reskin portfolio onto Instrument cards"
```

---

### Task 5: Reskin `team.html`

**Files:**
- Modify: `sprintsight/web/templates/team.html`
- Test: `tests/web/test_pages.py` (add a card assertion to an existing team test)

**Interfaces:**
- Consumes: shell blocks; `.card`, `.verdict-banner`/`.verdict-emoji`, `.detail`, `.rag`/`.badge`, `.audience-tabs`/`.audience-switch`/`.aud`/`.aud-active`, `.evidence-card`, `.report-body`, `.sources-list`, `.badge-live`.
- Produces: team page preserving: `red`, `status-atlas-s15`, `burn ratio`, `Status report`, `?audience=exec|programme|team`, `Risks`, `Recommended next step`, `verdict-banner`, `verdict-emoji`, `audience-tabs`, `class="aud`, and the `db_knowledge` live-DB panel.

- [ ] **Step 1: Add the failing assertion**

In `tests/web/test_pages.py`, extend `test_team_page_atlas_has_verdict_banner`:

```python
def test_team_page_atlas_has_verdict_banner(client):
    html = client.get("/team/atlas").text
    assert "verdict-banner" in html
    assert "verdict-emoji" in html
    assert 'class="card detail"' in html  # detail now in an Instrument card
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/web/test_pages.py::test_team_page_atlas_has_verdict_banner -q`
Expected: FAIL on `'class="card detail"'`.

- [ ] **Step 3: Reskin the template**

Replace the whole of `sprintsight/web/templates/team.html` with:

```html
{% extends "base.html" %}
{% block title %}{{ d.team }}{% endblock %}
{% block eyebrow %}Team{% endblock %}
{% block heading %}{{ d.team }}{% endblock %}
{% block sub %}<a class="lnk" href="/">&larr; Back to portfolio</a>{% endblock %}
{% block main %}

{% if d.has_verdict and d.is_watermelon %}
<div class="card verdict-banner">
  <span class="verdict-emoji">🍉</span>
  <div>
    <h2>{{ d.team }} <span class="badge badge-watermelon">watermelon</span></h2>
    <p class="sub">
      Reported <span class="rag rag-{{ d.reported_status }}">{{ d.reported_status }}</span>
      but computed actual <span class="rag rag-{{ d.actual_status }}">{{ d.actual_status }}</span>.
      The status looks healthier than the data supports.
    </p>
  </div>
</div>
{% endif %}

<div class="card detail">
{% if d.has_verdict %}
  {% if not d.is_watermelon %}
  <p>Reported <span class="rag rag-{{ d.reported_status }}">{{ d.reported_status }}</span>,
     computed actual <span class="rag rag-{{ d.actual_status }}">{{ d.actual_status }}</span>.</p>
  {% endif %}
  <h2>Why</h2>
  <p class="explanation">{{ d.explanation }}</p>
  <h2>Signals</h2>
  <ul class="signals">{% for s in d.signals %}<li>{{ s }}</li>{% endfor %}</ul>
  <h2>Evidence</h2>
  <ul class="evidence">
    {% for e in d.evidence %}
    <li class="evidence-card"><strong>{{ e.title }}</strong> <code>{{ e.artifact_id }}</code>
      {% if e.snippet %}<div class="snippet">{{ e.snippet }}</div>{% endif %}</li>
    {% endfor %}
  </ul>
{% else %}
  <p class="explanation">{{ d.explanation }}</p>
{% endif %}
</div>

{% if d.has_verdict %}
<div class="card">
  <h2>Status report</h2>
  <p class="audience-tabs audience-switch">
    {% for a in ["exec", "programme", "team"] %}
    <a href="/team/{{ d.team|lower }}?audience={{ a }}" class="aud{% if d.audience == a %} aud-active{% endif %}">{{ a|capitalize }}</a>
    {% endfor %}
  </p>
  {% if d.report_insufficient %}
    <p class="explanation">Not enough evidence to write a report.</p>
  {% else %}
    {% for s in d.report_sections %}
    <h3>{{ s.heading }}</h3>
    <p class="report-body">{{ s.body }}</p>
    {% endfor %}
    {% if d.report_sources %}
    <div class="sources-list">
      <h3>Sources</h3>
      <ul class="sources">
        {% for src in d.report_sources %}<li><strong>{{ src.title }}</strong> <code>{{ src.artifact_id }}</code></li>{% endfor %}
      </ul>
    </div>
    {% endif %}
  {% endif %}
</div>
{% endif %}

{% if d.db_knowledge %}
<div class="card">
  <h2>From the knowledge base <span class="badge badge-live">live DB</span></h2>
  <ul class="evidence db-knowledge">
    {% for kb in d.db_knowledge %}
    <li class="evidence-card"><strong>{{ kb.title }}</strong> <code>{{ kb.source_ref }}</code>
      <span class="kb-score">match {{ kb.score }}</span>
      {% if kb.snippet %}<div class="snippet">{{ kb.snippet }}</div>{% endif %}</li>
    {% endfor %}
  </ul>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 4: Run the team tests**

Run: `.venv/bin/pytest tests/web/test_pages.py -k team -q`
Expected: PASS (evidence/signals, verdict banner + card, report + audience switch, exec section).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/templates/team.html tests/web/test_pages.py
git commit -m "feat(web): reskin team drill-in onto Instrument cards"
```

---

### Task 6: Reskin `crosstool.html`

**Files:**
- Modify: `sprintsight/web/templates/crosstool.html`
- Test: `tests/web/test_pages.py` (add a card assertion to an existing crosstool test)

**Interfaces:**
- Consumes: shell blocks; `.summary-band`/`.kpi`, `.card`, `.table-wrap`/`table.table`, `.rag`/`.badge`/`.badge-stalled`, `.lnk`.
- Produces: crosstool page preserving: `summary-band`, `SSSB-1`, `SSSB-7`, `no activity`, `Jira SSSB-1`, `GitHub:`, `offline replay`, `live as of ...`, `offline (live read failed)`.

- [ ] **Step 1: Add the failing assertion**

In `tests/web/test_pages.py`, extend `test_crosstool_page_renders_summary_and_flags`:

```python
def test_crosstool_page_renders_summary_and_flags(client):
    html = client.get("/crosstool").text
    assert "summary-band" in html
    assert "SSSB-1" in html                     # a watermelon ticket
    assert "SSSB-7" in html                     # the stalled ticket
    assert "no activity" in html                # the stalled citation
    assert "Jira SSSB-1" in html                # both tools cited
    assert "GitHub:" in html
    assert 'class="card"' in html               # table now in an Instrument card
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/web/test_pages.py::test_crosstool_page_renders_summary_and_flags -q`
Expected: FAIL on `'class="card"'`.

- [ ] **Step 3: Reskin the template**

Replace the whole of `sprintsight/web/templates/crosstool.html` with:

```html
{% extends "base.html" %}
{% block title %}Cross-tool signals{% endblock %}
{% block eyebrow %}Cross-tool{% endblock %}
{% block heading %}Cross-tool signals{% endblock %}
{% block sub %}Jira status versus the actual GitHub activity, per ticket. <a class="lnk" href="/">&larr; Back to portfolio</a>{% endblock %}
{% block main %}
<div class="summary-band">
  <div class="kpi{% if page.summary.watermelons %} kpi-alert{% endif %}"><span class="num">{{ page.summary.watermelons }}</span><span class="label">Watermelons flagged</span></div>
  <div class="kpi"><span class="num">{{ page.summary.stalled }}</span><span class="label">Stalled PRs</span></div>
  <div class="kpi"><span class="num">{{ page.summary.checked }}</span><span class="label">Tickets checked</span></div>
</div>

<div class="card">
  <p class="lede">Data source:
    {% if page.summary.mode == 'live' %}<span class="badge badge-ok" title="Read live from Jira + GitHub">live as of {{ page.summary.as_of }}</span>
    {% elif page.summary.mode == 'offline-failed' %}<span class="badge badge-stalled" title="Live read failed; showing the saved snapshot">offline (live read failed)</span>
    {% else %}<span class="badge badge-ok" title="Saved snapshot, deterministic">offline replay</span>{% endif %}
  </p>
  <div class="table-wrap">
    <table class="table portfolio">
      <thead><tr><th>Ticket</th><th>Team</th><th>Reported</th><th>Actual</th><th>Flag</th><th>Evidence</th></tr></thead>
      <tbody>
      {% for row in page.rows %}
        <tr class="{{ 'watermelon' if row.classification == 'watermelon' else '' }}" title="{{ row.headline }}">
          <td>{{ row.key }}</td>
          <td>{{ row.team }}</td>
          <td><span class="rag rag-{{ row.reported_status }}">{{ row.reported_status }}</span></td>
          <td><span class="rag rag-{{ row.actual_status }}">{{ row.actual_status }}</span></td>
          <td>
            {% if row.classification == 'watermelon' %}<span class="badge badge-watermelon" title="Reported healthier than reality">watermelon</span>
            {% elif row.classification == 'stalled' %}<span class="badge badge-stalled" title="Open PR has gone quiet">stalled</span>
            {% else %}<span class="badge badge-ok">consistent</span>{% endif %}
          </td>
          <td class="evidence">{{ row.jira_citation }}<br>{{ row.github_citation }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Run the crosstool tests**

Run: `.venv/bin/pytest tests/web/test_pages.py -k crosstool -q`
Expected: PASS (summary+flags+card, offline badge, live badge, offline-failed badge).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/templates/crosstool.html tests/web/test_pages.py
git commit -m "feat(web): reskin cross-tool page onto Instrument cards"
```

---

### Task 7: Reskin `admin_accounts.html` + final verification + HANDOVER flag

**Files:**
- Modify: `sprintsight/web/templates/admin_accounts.html`
- Modify: `HANDOVER.md` (append one Learning queue line)
- Test: `tests/web/test_pages.py` (add a table assertion to the admin test)

**Interfaces:**
- Consumes: shell blocks; `.card`, `.table-wrap`/`table.table`, `.pill`/`.pill-ok`, `.lnk`.
- Produces: admin accounts page preserving the `Accounts` heading and the email/role rows.

- [ ] **Step 1: Add the failing assertion**

In `tests/web/test_pages.py`, extend `test_admin_accounts_uses_shell`:

```python
def test_admin_accounts_uses_shell(client):
    html = client.get("/admin/accounts").text
    assert 'data-app="sprintsight"' in html
    assert "Accounts" in html
    assert 'class="table"' in html  # Instrument table
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/web/test_pages.py::test_admin_accounts_uses_shell -q`
Expected: FAIL on `'class="table"'`.

- [ ] **Step 3: Reskin the template**

Replace the whole of `sprintsight/web/templates/admin_accounts.html` with:

```html
{% extends "base.html" %}
{% block title %}Accounts - Sprintsight{% endblock %}
{% block eyebrow %}Admin{% endblock %}
{% block heading %}Accounts{% endblock %}
{% block sub %}Admin only. Synthetic demo users. <a class="lnk" href="/">&larr; Back to portfolio</a>{% endblock %}
{% block main %}
<div class="card">
  <div class="table-wrap">
    <table class="table">
      <thead><tr><th>Email</th><th>Role</th></tr></thead>
      <tbody>
        {% for a in accounts %}
        <tr><td>{{ a.email }}</td><td><span class="pill pill-ok">{{ a.role }}</span></td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Run the admin test**

Run: `.venv/bin/pytest tests/web/test_pages.py::test_admin_accounts_uses_shell -q`
Expected: PASS.

- [ ] **Step 5: Full verification (suite + ruff + eval gates)**

Run: `.venv/bin/pytest -q`
Expected: PASS (all 340+ passing, 4 skipped unchanged; the new theme tests add to the count).

Run: `.venv/bin/ruff check .`
Expected: clean.

Run the deterministic eval gates and confirm they are unchanged:

```bash
.venv/bin/python scripts/run_watermelon_eval.py && .venv/bin/python scripts/run_report_eval.py && .venv/bin/python scripts/run_crosstool_eval.py
```

Expected: watermelon 4/4, report 4/4, cross-tool 7/7 (exact command names: confirm against the existing scripts in `scripts/`; if a name differs, use the script that the CI `lint-and-test` job runs).

- [ ] **Step 6: Append one HANDOVER Learning queue line**

In `HANDOVER.md`, under `## Learning queue`, append (no em dashes):

```
- Adopting a shared design system by faithful copy plus a drift guard | Sprintsight now wears the suite's Instrument skin (one shared stylesheet, self-hosted fonts, an icon sprite, the signature scope-trace animation), kept in step by a SHA test that flags any divergence from the suite source, without entangling the Python app in the suite's Node build tooling | sprintsight/web/static/theme/ + tests/web/test_theme_drift.py + suite-design-alignment slice | flagged 2026-06-30
```

- [ ] **Step 7: Commit**

```bash
git add sprintsight/web/templates/admin_accounts.html tests/web/test_pages.py HANDOVER.md
git commit -m "feat(web): reskin admin accounts; flag learning; finish Instrument alignment"
```

---

## Self-Review

**1. Spec coverage:**
- Vendor + serve theme assets at web-root -> Task 1.
- Instrument shell in `base.html` with `data-app="sprintsight"` -> Task 2.
- `sprintsight.css` (per-app tokens, indigo accent, separate RAG verdict set, components) -> Task 2.
- Reskin all five pages -> Tasks 3 (login), 4 (portfolio), 5 (team), 6 (crosstool), 7 (admin).
- Reticle glyph as a separate SVG referenced by the brand mark -> Task 1 (file) + Task 2 (referenced in `base.html`).
- Drift guard (SHA compare, skip when absent) -> Task 1.
- Updates to existing tests that assert old markup -> Task 2 (shell assertions in `test_pages.py`); reskin tasks each add one structure assertion.
- Remove `static/app.css` -> Task 2.
- Served-markup theme tests + watermelon-meaning preserved + asset links resolve to 200 -> Tasks 1, 2, and each reskin task.
- Eval gates unchanged + ruff + full suite -> Task 7.
- HANDOVER learning flag -> Task 7.
- Out of scope (CSP header, dark mode, full Node registration, folding the reticle into the suite sprite) -> not implemented, by design.

**2. Placeholder scan:** Every code/template/test step contains complete content. The only deliberate deferral is the exact eval-script names in Task 7 Step 5, which instructs confirming against the scripts the CI job runs (the scripts exist; their exact filenames are an environment detail, not a design gap).

**3. Type consistency:** Component class names are consistent across `sprintsight.css` and every template (`summary-band`, `kpi`, `kpi-alert`, `rag`/`rag-*`, `badge`/`badge-*`, `verdict-banner`, `verdict-emoji`, `audience-tabs`/`audience-switch`/`aud`/`aud-active`, `evidence-card`, `report-body`, `sources-list`, `login-card`, `login-form`, `error`, `kb-score`). The reticle symbol id `glyph-sprintsight` matches between `sprintsight.svg`, `base.html`, and the tests. The four mounts (`/css`, `/js`, `/illos`, `/fonts`) match the head links and Instrument's absolute URLs.
