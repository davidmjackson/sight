# Design — Cross-team dependency slip (moat Behaviour 1 + 3)

Date: 2026-07-01. Status: DRAFT for review. Jira: (to create, Stage 7 / moat).
Related: docs/moat/moat-behaviours.md (B1 LOCKED "not to be cut", B3), docs/evals/watermelon-eval.md.

## Plain-English summary (read this first)

A recent audit found that two of Sprintsight's three differentiating behaviours are real in
the code but effectively invisible in the demo. The weakest is the one the moat spec calls the
headline differentiator: "Team Atlas is blocked by Team Draco's slipping auth API." Today the
app only notices that Atlas mentioned a dependency in chat and never logged it. It never actually
reads Draco's side to confirm the auth API is genuinely slipping, and it never says any of this
out loud in the interface. You have to open an evidence snippet to see it at all.

This change makes that behaviour real and visible, in the smallest honest way:
- It actually reads Draco's own ticket (DRACO-412) and confirms the slip (due end of Sprint 14,
  now Sprint 16), so the claim is backed by both teams' data, not just Atlas's chat.
- It shows a clear card on Atlas's page naming both teams, the slipping item, and citing both
  sides, plus a "recommend logging this in the RAID" line (Behaviour 3's missing action).
- It puts a small "cross-team risk" marker on Atlas's row in the portfolio so it is visible
  before you drill in.

It does NOT build a general dependency-graph engine. It reconciles only a dependency that is
explicitly named in an artifact, which is exactly the scope the moat spec locked. One change
lands both Behaviour 1 and Behaviour 3, which share the same underlying signal today.

Nothing about the existing watermelon verdict changes. This is additive. No live data or
channels are needed; it runs on the synthetic corpus that already contains the seeded scenario.

## The problem (what the audit found)

- The detector's `_find_hidden_dependency` (`sprintsight/detector.py:88`) only reads Atlas's own
  Slack and checks it is absent from Atlas's RAID. It never pulls Draco's artifacts. The two
  teams are named only incidentally because the chat body says "Draco's auth API".
- In the UI this survives as one un-named line in a Signals list ("dependency raised in chat but
  missing from RAID", `team.html`) plus an evidence snippet you must click. No banner, no card.
- The `/crosstool` page is cross-TOOL (Jira vs GitHub), a different axis, so the demo has no
  cross-TEAM surface at all.
- Behaviour 3's defining action ("recommend logging it in the RAID") appears nowhere in the UI
  or evals.

The seeded data fully supports a real reconcile:
- Atlas chat `slack-atlas-s15-msg-dep` names `DRACO-412`, says it slipped to Sprint 16, and that
  it is "the reason our burndown's flat".
- Draco ticket `jira-draco-s15-authapi` has `source_ref: DRACO-412`, records the slip (originally
  due end of Sprint 14, current target Sprint 16), and names Atlas as the downstream consumer.
- Draco status `status-draco-s15` honestly flags the same slip.

## Scope decision (locked with the product owner)

Do a REAL cross-team reconcile, but MINIMAL, matching the moat spec's locked guardrail:
"reconcile discoverable dependencies only (a dependency named in an artifact), not inferred
links. No general dependency-graph engine for the showcase."

- Surface: Atlas team-page card AND a small portfolio-row marker (spec use cases 2 risk radar and
  3 portfolio roll-up).
- Covers Behaviour 1 and Behaviour 3 in one change.

## Design

### New module: `sprintsight/crossteam.py` (pure reconciler)

Mirrors the existing `sprintsight/crosstool.py` pattern (a separate pure reconciler that lives
outside the detector graph). Keeps the per-team detector contract clean and keeps `detector.py`
from growing a second responsibility.

Data model:

```python
@dataclass(frozen=True)
class CrossTeamRisk:
    consumer_team: str        # "Atlas"
    provider_team: str        # "Draco"
    dependency_ref: str       # "DRACO-412"
    dependency_label: str     # "Draco Auth API v2" (from the provider ticket title)
    slip_detail: str          # "due end of Sprint 14, now targeted at Sprint 16"
    logged_in_raid: bool      # False -> recommend logging (Behaviour 3)
    consumer_citation: str    # "slack-atlas-s15-msg-dep"
    provider_citations: list[str]  # ["jira-draco-s15-authapi", "status-draco-s15"]
    headline: str             # one-line, both teams named
```

Entry point:

```python
def reconcile_cross_team(
    consumer_team: str,
    consumer_arts: dict[str, Artifact],
    provider_arts_for: Callable[[str], dict[str, Artifact]],
) -> CrossTeamRisk | None:
```

Algorithm (deterministic, explainable):
1. In the consumer's Slack/chat artifacts, find dependency references matching `[A-Za-z]+-\d+`
   (e.g. "DRACO-412") that appear alongside risk language (reuse the existing dependency/risk
   regex vocabulary from `_find_hidden_dependency` so the two stay consistent).
2. Map the ref prefix to a provider team ("DRACO" -> "Draco"). If the prefix is the consumer's
   own team, skip (not cross-team).
3. Load provider artifacts via the injected `provider_arts_for(provider_team)` seam. Find the
   artifact whose `meta["source_ref"]` equals the ref (falls back to artifact_id/title contains).
4. Confirm the provider item is SLIPPING: slip language (`slipp|delayed|pushed to sprint N|
   carried over|now targeted`) in the provider ticket title/body AND the item is not done/closed.
   If not slipping, return None (do not cry wolf: a named dependency that is on track is not a
   risk).
5. Determine `logged_in_raid`: is the ref (or the dependency label) present in the consumer's
   Sprint-15 RAID body? If absent, set `logged_in_raid=False` (recommend logging).
6. Build `CrossTeamRisk` with citations to both sides and a headline that names both teams.
   Return None if no qualifying dependency is found.

Guardrails (YAGNI): only refs explicitly present in an artifact; one provider lookup per named
ref; no transitive/inferred dependencies; no graph. Recommend-only: this module never writes to
any RAID (moat principle). It returns a finding for a human.

### Wiring into the web layer (`sprintsight/web/service.py`)

- Add `provider_arts_for = _artifacts_for` as the seam, so the reconcile uses the SAME corpus/DB
  path already in place (works offline today, DB when the verdict-DB gate is on; fail-safe).
- `team_detail(team_id)`: after the verdict, call `reconcile_cross_team(team, arts, _artifacts_for)`
  and attach the result to `TeamDetail` as `cross_team_risk: CrossTeamRisk | None`. Reuse the
  already-fetched consumer `arts`; only the provider load is extra, and only when a ref names one.
- `portfolio()`: set `has_cross_team_risk: bool` on `TeamRow` by running the same reconcile per
  team (returns quickly to None for teams with no named cross-team dependency). To stay consistent
  with the recent fetch-once cleanup, `portfolio()` fetches each team's artifacts ONCE and passes
  them to both `_verdict_from_arts` and the reconcile, rather than re-fetching (no third DB
  round-trip when the verdict-DB gate is on).

### Templates

- `team.html`: a prominent card (near the verdict banner) when `cross_team_risk` is present:
  headline ("Atlas is blocked by Draco's slipping Auth API v2 (DRACO-412)"), the slip detail,
  "Cited in: <Atlas chat> and <Draco ticket / status>", and, when `not logged_in_raid`, a
  "Recommend: log this in Atlas's RAID with an owner and mitigation" line. Styling reuses the
  existing Instrument card/verdict classes; indigo accent, not the red/amber/green verdict set.
- `portfolio.html`: a small "cross-team risk" marker/badge on a row when `has_cross_team_risk`.

### What stays unchanged (additive, low risk)

- The watermelon verdict, its signals, and its evidence list are untouched. The existing
  detector signal ("dependency raised in chat but missing from RAID") and the
  `slack-atlas-s15-msg-dep` evidence citation STAY, so current watermelon evals keep passing.
- No detector graph change. Cross-team reconcile is a function the web layer calls alongside the
  verdict, exactly as `crosstool` is handled.

## Eval-first plan (no feature code before its eval exists)

New tests (write first, watch them fail, then implement):

1. `tests/test_crossteam.py` (pure unit):
   - Given real Atlas + Draco artifacts: `reconcile_cross_team("Atlas", atlas_arts, provider)`
     returns a `CrossTeamRisk` with `provider_team == "Draco"`, `dependency_ref == "DRACO-412"`,
     `logged_in_raid is False`, `consumer_citation == "slack-atlas-s15-msg-dep"`, and
     `jira-draco-s15-authapi` in `provider_citations`. Headline names both teams.
   - Negative: a consumer with no cross-team named dependency returns None.
   - Do-not-cry-wolf: if the provider ticket is patched to a non-slipping/done state, returns None.
   - RAID-present guard: if the ref is patched into the consumer RAID, `logged_in_raid is True`
     (no "recommend logging").
2. `tests/web/test_service.py` additions: `team_detail("atlas").cross_team_risk` is populated and
   names Draco; a team without the scenario has `cross_team_risk is None`. `portfolio()` sets
   `has_cross_team_risk` True for Atlas, False for the others.
3. `tests/web/test_pages.py` addition: the Atlas page renders the cross-team card text (both team
   names + "recommend"); the portfolio renders Atlas's marker.
4. Ground truth: add a cross-team assertion for Atlas-s15 to `data/ground-truth/labels.yaml`
   (expected provider `DRACO-412`, both citations) and assert it in the eval so the moat behaviour
   is covered by the deterministic gate, not only unit tests.

Full suite (currently 370 passed + 4 skipped) must stay green; ruff clean; existing watermelon /
report / cross-tool eval gates unchanged.

## Security and privacy

- Recommend-only, no writes: the reconciler never mutates a RAID or any store. It surfaces a
  finding for a human, consistent with moat principle B3 and the human-in-the-loop rule.
- No new external calls, no new data persistence, no new secrets. Runs on the local corpus (or
  the already-gated DB path). Nothing to flag under the security-first principle.

## Out of scope (YAGNI)

- No general dependency-graph engine, no inferred/transitive dependencies.
- No auto-writing to the RAID.
- No new connectors or live-data work.
- No change to the watermelon verdict logic or thresholds.

## Files touched

- New: `sprintsight/crossteam.py`, `tests/test_crossteam.py`.
- Edit: `sprintsight/web/service.py` (attach `cross_team_risk` / `has_cross_team_risk`),
  `sprintsight/web/templates/team.html`, `sprintsight/web/templates/portfolio.html`,
  `tests/web/test_service.py`, `tests/web/test_pages.py`, `data/ground-truth/labels.yaml`,
  and the watermelon eval assertion file if the ground-truth gate needs a new check.
```
