# Cross-Team Dependency Slip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the moat's cross-team dependency-slip behaviour (Behaviour 1) and the RAID-gap recommendation (Behaviour 3) real and visible in the demo, via a minimal real reconcile of a dependency that is explicitly named in an artifact.

**Architecture:** A new pure module `sprintsight/crossteam.py` reconciles a dependency named in a consumer team's chat (e.g. Atlas naming `DRACO-412`) against the provider team's own artifacts (Draco's ticket), confirms the provider item is slipping, and reports a `CrossTeamRisk` citing both sides plus a "recommend logging in the RAID" flag. It mirrors the existing `sprintsight/crosstool.py` reconciler and lives OUTSIDE the detector graph, so the per-team watermelon verdict is untouched. The web layer calls it alongside the verdict and surfaces a card on the team page and a marker on the portfolio row.

**Tech Stack:** Python 3, dataclasses, `re`, FastAPI + Jinja2 templates, pytest. No new dependencies.

## Global Constraints

- Eval-first: no feature code before the test that exercises it exists. Write the failing test first every time.
- Recommend-only: the reconciler NEVER writes to any RAID or store. It returns a finding for a human (moat principle B3).
- Additive only: do NOT change the watermelon verdict, its signals, its evidence, `detector.py`, or the detector graph. Existing gates (watermelon 4/4, report 4/4, cross-tool 7/7) must stay green.
- Scope guardrail (from the moat spec, LOCKED): reconcile ONLY dependencies explicitly named in an artifact. No general dependency-graph engine, no inferred/transitive links.
- No em dashes in any user-facing copy (project style).
- Do NOT edit vendored theme assets under the drift-guarded theme dirs. `sprintsight/web/templates/*.html` are app templates and are safe to edit. Add no new CSS files.
- After each task: the touched tests pass. Before the final handoff: full suite green (currently 370 passed + 4 skipped) and `ruff check` clean.
- Corpus facts you can rely on (already seeded): Atlas chat `slack-atlas-s15-msg-dep` names `DRACO-412`; Draco ticket `jira-draco-s15-authapi` has frontmatter `source_ref: DRACO-412`, a body Summary row `| Summary | Draco Auth API v2 |`, and body text "Slipped to Sprint 16"; `raid-atlas-s15` does NOT mention the Draco dependency.

---

### Task 1: Pure cross-team reconciler (`crossteam.py`)

**Files:**
- Create: `sprintsight/crossteam.py`
- Test: `tests/test_crossteam.py`

**Interfaces:**
- Consumes: `sprintsight.evals.fixtures.Artifact` (fields: `artifact_id`, `source_type`, `team`, `sprint`, `meta: dict`, `body: str`) and `artifacts_for(team, sprints)`.
- Produces:
  - `CrossTeamRisk` frozen dataclass with fields: `consumer_team: str`, `provider_team: str`, `dependency_ref: str`, `dependency_label: str`, `slip_detail: str`, `logged_in_raid: bool`, `consumer_citation: str`, `provider_citations: list[str]`, `headline: str`.
  - `reconcile_cross_team(consumer_team: str, consumer_arts: dict[str, Artifact], provider_arts_for: Callable[[str], dict[str, Artifact]]) -> CrossTeamRisk | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_crossteam.py`:

```python
from dataclasses import replace

from sprintsight.crossteam import CrossTeamRisk, reconcile_cross_team
from sprintsight.evals.fixtures import artifacts_for

SPRINTS = [14, 15]


def _provider():
    """Real corpus provider loader, case-insensitive by team name."""
    return lambda team: artifacts_for(team, SPRINTS)


def test_atlas_draco_slip_is_reconciled():
    risk = reconcile_cross_team("Atlas", artifacts_for("Atlas", SPRINTS), _provider())
    assert isinstance(risk, CrossTeamRisk)
    assert risk.consumer_team == "Atlas"
    assert risk.provider_team == "Draco"
    assert risk.dependency_ref == "DRACO-412"
    assert "Auth API" in risk.dependency_label
    assert risk.consumer_citation == "slack-atlas-s15-msg-dep"
    assert "jira-draco-s15-authapi" in risk.provider_citations
    # Behaviour 3: the dependency is NOT in Atlas's RAID -> recommend logging it.
    assert risk.logged_in_raid is False
    # Headline names BOTH teams and the slip.
    assert "Atlas" in risk.headline and "Draco" in risk.headline
    assert "sprint 16" in risk.headline.lower()


def test_boreas_has_no_cross_team_risk():
    risk = reconcile_cross_team("Boreas", artifacts_for("Boreas", SPRINTS), _provider())
    assert risk is None


def test_does_not_cry_wolf_when_provider_not_slipping():
    """If the named provider ticket is NOT slipping, there is no risk."""
    atlas = artifacts_for("Atlas", SPRINTS)
    draco = artifacts_for("Draco", SPRINTS)
    # Patch the Draco ticket body to a delivered/on-time state (no slip language).
    tid = "jira-draco-s15-authapi"
    draco[tid] = replace(
        draco[tid],
        body="| Summary | Draco Auth API v2 |\n| Status | Done |\nDelivered on time in Sprint 15.",
    )

    def provider(team):
        return draco if team.lower() == "draco" else artifacts_for(team, SPRINTS)

    assert reconcile_cross_team("Atlas", atlas, provider) is None


def test_logged_in_raid_when_dependency_is_recorded():
    """If Atlas HAS logged the ref in its RAID, logged_in_raid is True (no 'recommend logging')."""
    atlas = artifacts_for("Atlas", SPRINTS)
    raid_id = "raid-atlas-s15"
    atlas[raid_id] = replace(
        atlas[raid_id],
        body=atlas[raid_id].body + "\n| R-ATLAS-99 | DRACO-412 auth API slip | owner: Priya |",
    )
    risk = reconcile_cross_team("Atlas", atlas, _provider())
    assert risk is not None
    assert risk.logged_in_raid is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_crossteam.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sprintsight.crossteam'`.

- [ ] **Step 3: Write the implementation**

Create `sprintsight/crossteam.py`:

```python
"""Cross-team dependency-slip reconciler (moat Behaviour 1 + 3).

Pure and recommend-only. Given a dependency a consumer team names in its own chat
(e.g. Atlas naming Draco's DRACO-412), this reads the PROVIDER team's own artifacts,
confirms the item is genuinely slipping, and reports a CrossTeamRisk citing both sides.
It also flags whether the consumer logged the dependency in its RAID (Behaviour 3's
"recommend logging it"). It never writes anything.

Scope guardrail (moat spec, LOCKED): only dependencies explicitly named in an artifact
are reconciled. No general dependency-graph engine, no inferred links.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from sprintsight.evals.fixtures import Artifact

# A Jira-style reference like DRACO-412 (team prefix + number).
_REF = re.compile(r"[A-Za-z]{2,}-\d+")
# Risk + dependency vocabulary, consistent with detector._find_hidden_dependency.
_RISK = re.compile(r"isn't ready|not ready|slipp|bite us|won't hold|blocked|building on sand|late", re.I)
_DEP = re.compile(r"api|dependency|endpoint|service", re.I)
# The provider item is slipping if it uses slip language and is not marked done/closed.
_SLIP = re.compile(r"slipp|delayed|pushed to sprint|carried over|now targeted", re.I)
_DONE = re.compile(r"status[^\n|]*[|:]\s*(done|closed|shipped|released)", re.I)
_SLIP_TO = re.compile(r"slipp\w*\s+to\s+(sprint\s*\d+)", re.I)
_SUMMARY = re.compile(r"\|\s*Summary\s*\|\s*([^|]+?)\s*\|", re.I)


@dataclass(frozen=True)
class CrossTeamRisk:
    consumer_team: str
    provider_team: str
    dependency_ref: str
    dependency_label: str
    slip_detail: str
    logged_in_raid: bool
    consumer_citation: str
    provider_citations: list[str] = field(default_factory=list)
    headline: str = ""


def _provider_from_ref(ref: str) -> str:
    return ref.split("-")[0].title()


def _consumer_raid_body(consumer_arts: dict[str, Artifact]) -> str:
    for a in consumer_arts.values():
        if a.source_type == "raid" and a.sprint == 15:
            return a.body.lower()
    return ""


def _find_provider_ticket(ref: str, arts: dict[str, Artifact]) -> Artifact | None:
    for a in arts.values():
        if str(a.meta.get("source_ref", "")).upper() == ref.upper():
            return a
    for a in arts.values():
        if ref.lower() in a.artifact_id.lower():
            return a
    return None


def _summary(body: str, fallback: str) -> str:
    m = _SUMMARY.search(body)
    return m.group(1).strip() if m else fallback


def _slip_detail(body: str) -> str:
    m = _SLIP_TO.search(body)
    return f"slipped to {m.group(1)}" if m else "flagged as slipping on the provider side"


def _clean_label(label: str, provider_team: str) -> str:
    words = label.split()
    if words and words[0].lower() == provider_team.lower():
        return " ".join(words[1:])
    return label


def reconcile_cross_team(
    consumer_team: str,
    consumer_arts: dict[str, Artifact],
    provider_arts_for: Callable[[str], dict[str, Artifact]],
) -> CrossTeamRisk | None:
    raid_body = _consumer_raid_body(consumer_arts)
    for a in consumer_arts.values():
        if a.source_type != "slack" or a.sprint != 15:
            continue
        if not (_RISK.search(a.body) and _DEP.search(a.body)):
            continue
        for ref in _REF.findall(a.body):
            provider_team = _provider_from_ref(ref)
            if provider_team.lower() == consumer_team.lower():
                continue  # a self-reference is not cross-team
            provider_arts = provider_arts_for(provider_team)
            ticket = _find_provider_ticket(ref, provider_arts)
            if ticket is None:
                continue  # provider/ticket not tracked -> cannot reconcile
            if not _SLIP.search(ticket.body) or _DONE.search(ticket.body):
                continue  # named but on track -> do not cry wolf
            label = _summary(ticket.body, ref)
            logged = ref.lower() in raid_body or label.lower() in raid_body
            slip = _slip_detail(ticket.body)
            others = [
                x.artifact_id
                for x in provider_arts.values()
                if x.artifact_id != ticket.artifact_id
                and ref.lower() in x.body.lower()
                and x.source_type in {"raid", "status", "confluence"}
            ]
            clean = _clean_label(label, provider_team)
            headline = (
                f"{consumer_team} is blocked by {provider_team}'s {clean} "
                f"({ref}), which {slip}."
            )
            return CrossTeamRisk(
                consumer_team=consumer_team,
                provider_team=provider_team,
                dependency_ref=ref,
                dependency_label=label,
                slip_detail=slip,
                logged_in_raid=logged,
                consumer_citation=a.artifact_id,
                provider_citations=[ticket.artifact_id] + others,
                headline=headline,
            )
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_crossteam.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add sprintsight/crossteam.py tests/test_crossteam.py
git commit -m "feat(crossteam): pure cross-team dependency-slip reconciler [SS-5]"
```

---

### Task 2: Ground-truth eval gate for the moat behaviour

**Files:**
- Test: `tests/test_crossteam_eval.py`

**Interfaces:**
- Consumes: `reconcile_cross_team` (Task 1), `sprintsight.evals.fixtures.load_ground_truth` and `artifacts_for`.
- Produces: nothing new; ties the reconciler to the `dependency_thread` block in `data/ground-truth/labels.yaml` so the moat behaviour is covered by a deterministic gate, not only unit tests.

- [ ] **Step 1: Write the failing test**

Create `tests/test_crossteam_eval.py`:

```python
"""Deterministic moat gate: the reconciler must reproduce the authored dependency_thread
(Atlas depends on Draco's DRACO-412 auth API, slipped, unlogged in Atlas's RAID)."""

from sprintsight.crossteam import reconcile_cross_team
from sprintsight.evals.fixtures import artifacts_for, load_ground_truth

SPRINTS = [14, 15]


def test_reconciler_matches_ground_truth_dependency_thread():
    thread = load_ground_truth()["dependency_thread"]
    consumer = thread["consumer_team"]
    risk = reconcile_cross_team(
        consumer,
        artifacts_for(consumer, SPRINTS),
        lambda team: artifacts_for(team, SPRINTS),
    )
    assert risk is not None
    assert risk.provider_team == thread["provider_team"]
    assert risk.dependency_ref == thread["provider_ticket"]
    assert risk.consumer_citation == thread["raised_in"]
    # It reconciles from the provider's own ticket.
    assert thread["reconcilable_from"][0] in risk.provider_citations
    # The authored truth says it is missing from Atlas's RAID -> we recommend logging it.
    assert "raid-atlas-s15" in thread["missing_from"]
    assert risk.logged_in_raid is False
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `python -m pytest tests/test_crossteam_eval.py -v`
Expected: PASS (Task 1 already satisfies it; this test locks the behaviour to the authored ground truth). If it fails, the reconciler and the labels have drifted — fix the reconciler, not the labels.

- [ ] **Step 3: Commit**

```bash
git add tests/test_crossteam_eval.py
git commit -m "test(crossteam): ground-truth gate ties reconciler to dependency_thread [SS-5]"
```

---

### Task 3: Surface the risk on the team page (`service.team_detail`)

**Files:**
- Modify: `sprintsight/web/service.py`
- Test: `tests/web/test_service.py`

**Interfaces:**
- Consumes: `reconcile_cross_team`, `CrossTeamRisk` (Task 1); existing `_artifacts_for(team)`, `team_detail(team_id, audience)`, `TeamDetail`.
- Produces: `TeamDetail.cross_team_risk: CrossTeamRisk | None` (default `None`), populated by `team_detail` using the already-fetched `arts` and `_artifacts_for` as the provider loader.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_service.py`:

```python
def test_team_detail_atlas_has_cross_team_risk():
    d = service.team_detail("atlas")
    assert d is not None
    risk = d.cross_team_risk
    assert risk is not None
    assert risk.provider_team == "Draco"
    assert risk.dependency_ref == "DRACO-412"
    assert risk.logged_in_raid is False


def test_team_detail_boreas_has_no_cross_team_risk():
    d = service.team_detail("boreas")
    assert d is not None
    assert d.cross_team_risk is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/web/test_service.py -k cross_team -v`
Expected: FAIL with `AttributeError: 'TeamDetail' object has no attribute 'cross_team_risk'`.

- [ ] **Step 3: Implement**

In `sprintsight/web/service.py`:

1. Add the import near the other `sprintsight` imports:

```python
from sprintsight.crossteam import CrossTeamRisk, reconcile_cross_team
```

2. Add a field to the `TeamDetail` dataclass (after `db_knowledge`):

```python
    cross_team_risk: CrossTeamRisk | None = None
```

3. In `team_detail`, after `verdict = _verdict_from_arts(team, arts)` and the `if verdict is None:` guard, compute the risk from the artifacts already in hand and pass it through:

```python
    cross_team_risk = reconcile_cross_team(team, arts, _artifacts_for)
```

Then add `cross_team_risk=cross_team_risk,` to the `TeamDetail(...)` constructor call.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/web/test_service.py -v`
Expected: all pass (new cross_team tests plus the existing suite).

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/service.py tests/web/test_service.py
git commit -m "feat(web): attach cross-team risk to the team drill-in [SS-5]"
```

---

### Task 4: Flag the risk on the portfolio row (`service.portfolio`)

**Files:**
- Modify: `sprintsight/web/service.py`
- Test: `tests/web/test_service.py`

**Interfaces:**
- Consumes: `reconcile_cross_team` (Task 1); existing `portfolio()`, `TeamRow`, `_artifacts_for`, `_verdict_from_arts`, `_insufficient_row`.
- Produces: `TeamRow.has_cross_team_risk: bool` (default `False`), set by `portfolio()` which now fetches each team's artifacts ONCE and reuses them for both the verdict and the reconcile.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_service.py`:

```python
def test_portfolio_flags_atlas_cross_team_risk():
    atlas = _row(service.portfolio(), "Atlas")
    assert atlas.has_cross_team_risk is True


def test_portfolio_other_teams_have_no_cross_team_risk():
    rows = {r.team: r for r in service.portfolio()}
    for team in ("Boreas", "Cygnus", "Draco", "Echo"):
        assert rows[team].has_cross_team_risk is False, team
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/web/test_service.py -k cross_team_risk -v`
Expected: FAIL with `AttributeError: 'TeamRow' object has no attribute 'has_cross_team_risk'`.

- [ ] **Step 3: Implement**

In `sprintsight/web/service.py`:

1. Add a field to the `TeamRow` dataclass (after `has_verdict`):

```python
    has_cross_team_risk: bool = False
```

2. Rewrite `portfolio()` to fetch once per team and reuse for verdict + reconcile:

```python
def portfolio() -> list[TeamRow]:
    rows: list[TeamRow] = []
    for team in TEAMS:
        arts = _artifacts_for(team)  # fetched once; reused for verdict and reconcile
        verdict = _verdict_from_arts(team, arts)
        if verdict is None:
            rows.append(_insufficient_row(team))
            continue
        has_risk = reconcile_cross_team(team, arts, _artifacts_for) is not None
        rows.append(
            TeamRow(
                team=team,
                reported_status=verdict.reported_status,
                actual_status=verdict.actual_status,
                is_watermelon=verdict.is_watermelon,
                headline=_headline(verdict),
                has_verdict=True,
                has_cross_team_risk=has_risk,
            )
        )
    return rows
```

(Leave `_verdict_or_none` defined; it is a harmless thin wrapper. `_insufficient_row` keeps `has_cross_team_risk` at its `False` default.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/web/test_service.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sprintsight/web/service.py tests/web/test_service.py
git commit -m "feat(web): flag cross-team risk on the portfolio row [SS-5]"
```

---

### Task 5: Render the card and the portfolio marker

**Files:**
- Modify: `sprintsight/web/templates/team.html`
- Modify: `sprintsight/web/templates/portfolio.html`
- Test: `tests/web/test_pages.py`

**Interfaces:**
- Consumes: `TeamDetail.cross_team_risk` (Task 3) as `d.cross_team_risk`; `TeamRow.has_cross_team_risk` (Task 4) as `row.has_cross_team_risk`.
- Produces: rendered HTML only (no Python interface).

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_pages.py`:

```python
def test_team_page_atlas_shows_cross_team_card(client):
    html = client.get("/team/atlas").text
    assert "cross-team-risk" in html          # the card marker class
    assert "Draco" in html                     # provider named
    assert "DRACO-412" in html                 # dependency ref cited
    assert "slack-atlas-s15-msg-dep" in html   # consumer-side citation
    assert "jira-draco-s15-authapi" in html    # provider-side citation
    assert "Recommend" in html                 # Behaviour 3: recommend logging in the RAID


def test_team_page_boreas_has_no_cross_team_card(client):
    html = client.get("/team/boreas").text
    assert "cross-team-risk" not in html


def test_portfolio_marks_atlas_cross_team_row(client):
    html = client.get("/").text
    assert "cross-team" in html                # Atlas row marker text/class
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/web/test_pages.py -k cross_team -v`
Expected: FAIL (the strings are not in the rendered HTML yet).

- [ ] **Step 3: Implement the team-page card**

In `sprintsight/web/templates/team.html`, insert this block immediately AFTER the watermelon `verdict-banner` block (after its `{% endif %}` on the line that currently ends at line 20), BEFORE `<div class="card detail">`:

```html
{% if d.cross_team_risk %}
{% set r = d.cross_team_risk %}
<div class="card cross-team-risk">
  <h2>Cross-team risk <span class="badge badge-eyebrow">{{ r.provider_team }} dependency</span></h2>
  <p class="sub">{{ r.headline }}</p>
  <p>Cited on both sides:
    <code>{{ r.consumer_citation }}</code>
    {% for c in r.provider_citations %}<code>{{ c }}</code>{% endfor %}
  </p>
  {% if not r.logged_in_raid %}
  <p class="recommend"><strong>Recommend:</strong> log this dependency in {{ r.consumer_team }}'s RAID with an owner and a mitigation. (Sprintsight recommends only; it does not write to the RAID.)</p>
  {% endif %}
</div>
{% endif %}
```

- [ ] **Step 4: Implement the portfolio marker**

In `sprintsight/web/templates/portfolio.html`, replace the `Flag` cell (the `<td>` currently spanning lines 27 to 31) with a version that appends a cross-team marker:

```html
          <td>
            {% if not row.has_verdict %}<span class="badge badge-muted">insufficient evidence</span>
            {% elif row.is_watermelon %}<span class="badge badge-watermelon" title="Reported healthier than reality">watermelon</span>
            {% else %}<span class="badge badge-ok">consistent</span>{% endif %}
            {% if row.has_cross_team_risk %}<span class="badge badge-eyebrow cross-team" title="A cross-team dependency is slipping">cross-team risk</span>{% endif %}
          </td>
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/web/test_pages.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add sprintsight/web/templates/team.html sprintsight/web/templates/portfolio.html tests/web/test_pages.py
git commit -m "feat(web): render cross-team risk card + portfolio marker [SS-5]"
```

---

### Task 6: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite offline**

Run: `python -m pytest -q`
Expected: previous count plus the new tests, all green (was 370 passed + 4 skipped; expect ~382 passed + 4 skipped). No failures. In particular the watermelon (4/4), report (4/4), and cross-tool (7/7) gates are unchanged.

- [ ] **Step 2: Lint**

Run: `ruff check sprintsight tests`
Expected: no errors. If `badge-eyebrow` or `cross-team` need CSS to look right, that is cosmetic and out of scope; the classes render regardless.

- [ ] **Step 3: Confirm the moat behaviours now land (manual sanity, optional)**

If running the app locally, load `/team/atlas` and confirm the cross-team card shows "Atlas is blocked by Draco's Auth API v2 (DRACO-412), which slipped to Sprint 16", both citations, and the Recommend line; load `/` and confirm Atlas's row shows the "cross-team risk" marker and no other team does.

- [ ] **Step 4: Final commit if anything was adjusted**

```bash
git add -A
git commit -m "chore(crossteam): full-suite green + lint clean [SS-5]"
```

---

## Self-review notes (author)

- **Spec coverage:** reconciler (Task 1), cross-team + RAID-gap surfaced with both citations and the recommend-logging line (Tasks 3/5), portfolio marker (Tasks 4/5), eval-first with do-not-cry-wolf + RAID-present guards (Task 1) and a ground-truth gate (Task 2), additive/no verdict change (constraints + Tasks 3/4 leave detector untouched), recommend-only (Task 1 + card copy). All spec sections map to a task.
- **No new deps, no external calls, no persistence** — matches the security note in the spec.
- **False-positive check:** verified against the corpus — Cygnus names `PLAT-288` (untracked provider) and `CYG-141` (resolves to team "Cyg" != "Cygnus", empty); Draco names its own `DRACO-417` (self-reference skipped). Only Atlas produces a risk.
```
