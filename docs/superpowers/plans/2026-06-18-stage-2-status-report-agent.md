# Stage 2 — Status Report Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, audience-tuned, fully-cited status-report agent that turns the locked SS-1.5 report-quality eval green, refusing to fabricate on thin data.

**Architecture:** New `sprintsight/report/` package (contract + audience profiles + deterministic composer behind a `ReportWriter` callable seam) and a `sprintsight/evals/report.py` suite built on the existing harness. Eval-first: it lands RED with a null writer, then the composer turns it GREEN. The composer reuses the detector's `parse_metrics`/`parse_reported_status`; the eval checks grounding independently against `data/ground-truth/labels.yaml`. No network, no Anthropic key — runs in CI. The LLM-backed writer is a deferred drop-in behind the same callable.

**Tech Stack:** Python 3.11, dataclasses, `re`, PyYAML (via existing `fixtures.py`), pytest, ruff.

## Global Constraints

- Python >= 3.11; ruff lint select = E, F, I, UP, B (line-length 100). All code must pass `ruff check .`.
- Deterministic only: no LLM calls, no network, no Anthropic key in the eval path (ZDR-clean).
- Eval-first: no composer code lands before the report eval exists and is RED (Story A).
- Reuse, don't duplicate: metric/RAG parsing comes from `sprintsight.detector` (`parse_metrics`, `parse_reported_status`, `Metrics`).
- Report contract (SS-1.5 §2): `Report{team, audience, sections: dict[str,str], claims: list[Claim], insufficient_evidence: bool}`; `Claim{text: str, citations: list[str]}`.
- Audience profiles are LOCKED (report-quality-eval.md §4): exec ~150 words / programme ~400 words / team uncapped; required sections and forbidden markers per profile.
- The watermelon eval and its corpus stay untouched in behaviour; adding team **Echo** must not change its 4 hardcoded teams.
- Jira: each Story walked Backlog→To Do→In Progress→In Review→Done one transition at a time, with an AC-check completion comment (docs/jira/workflow.md). Board moves are operational, performed outside this code plan.

---

## File Structure

- `data/corpus/echo/status-echo-s15.md` — NEW. The thin 5th-team artifact (one-line status, no metrics/RAID/chat).
- `data/ground-truth/labels.yaml` — MODIFY. Add a sparse Echo s15 record.
- `tests/test_fixtures.py` — MODIFY. Bump record count 8→9 and corpus count 36→37; add Echo thinness assertion.
- `tests/test_ingest.py` — MODIFY. Bump corpus counts 36→37.
- `.github/workflows/ci.yml` — MODIFY. Bump corpus counts 36→37; add the report-eval gate step.
- `sprintsight/report/__init__.py` — NEW. Package marker.
- `sprintsight/report/contract.py` — NEW. `Claim`, `Report` dataclasses.
- `sprintsight/report/audience.py` — NEW. `AudienceProfile`, `PROFILES`, marker regexes/terms.
- `sprintsight/report/writer.py` — NEW. `ReportWriter` type alias, `null_writer`, `compose` (the deterministic composer).
- `sprintsight/evals/report.py` — NEW. Assertions A–F, `build_cases`, `run_report_eval`.
- `scripts/run_report_eval.py` — NEW. Scoreboard entrypoint; exits non-zero unless fully green.
- `tests/test_report_contract.py`, `tests/test_audience.py`, `tests/test_report_eval.py`, `tests/test_report_writer.py` — NEW. Unit + suite tests.

---

# STORY A — Echo thin fixture + report eval landing RED

Deliverable: the SS-1.5 report eval is wired to the corpus and bites; with the null writer the suite is RED, and a committed test asserts that RED state (so CI stays green). No composer yet.

### Task A1: Add the Echo thin-data team to the corpus

**Files:**
- Create: `data/corpus/echo/status-echo-s15.md`
- Modify: `data/ground-truth/labels.yaml` (append Echo record)
- Modify: `tests/test_fixtures.py` (counts 8→9, 36→37; add thinness check)
- Modify: `tests/test_ingest.py` (counts 36→37)
- Modify: `.github/workflows/ci.yml` (counts 36→37)
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Produces: a corpus artifact `status-echo-s15` (team `Echo`, sprint 15) with no metric line, no burndown/RAID/chat siblings; a ground-truth record `{team: Echo, sprint: 15, expected_evidence: [status-echo-s15], insufficient_evidence: true}`. Consumed by the report eval's Case 3.

- [ ] **Step 1: Update the corpus-count tests to the new total (fails first)**

In `tests/test_fixtures.py`, change the two assertions and the comment:

```python
def test_ground_truth_shape():
    gt = load_ground_truth()
    assert set(gt["sprints"]) == {"14", "15"}
    records = gt["records"]
    assert len(records) == 9  # 4 teams x 2 sprints + Echo s15 (thin-data trap)

    atlas_s15 = next(r for r in records if r["team"] == "Atlas" and r["sprint"] == 15)
    assert atlas_s15["is_watermelon"] is True
    assert atlas_s15["reported_status"] == "green"
    assert atlas_s15["actual_status"] == "red"
```

```python
def test_corpus_complete():
    corpus = load_corpus()
    assert len(corpus) == 37
```

And add a new test at the end of the file:

```python
def test_echo_is_thin():
    # The fabrication trap: Echo has only a one-line status, no burndown/RAID/chat.
    corpus = load_corpus()
    echo = [aid for aid in corpus if aid.endswith("echo-s15")]
    assert echo == ["status-echo-s15"]
    body = corpus["status-echo-s15"].body
    assert "Committed" not in body and "Velocity" not in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_fixtures.py -q`
Expected: FAIL — `test_ground_truth_shape` (records still 8), `test_corpus_complete` (corpus still 36), `test_echo_is_thin` (no Echo artifact yet).

- [ ] **Step 3: Create the Echo artifact**

Create `data/corpus/echo/status-echo-s15.md`:

```markdown
---
artifact_id: status-echo-s15
source_type: confluence
source_ref: ECHO-STATUS-S15
title: "Echo — Sprint 15 Status"
author: "Sam Reilly (Delivery Lead)"
source_timestamp: 2026-05-29T16:00:00Z
team: Echo
sprint: 15
---

# Echo — Sprint 15 Status

Sprint 15: green, nothing to report.
```

- [ ] **Step 4: Append the sparse Echo ground-truth record**

At the end of `data/ground-truth/labels.yaml`, append:

```yaml

  # ================= ECHO — THIN-DATA TRAP (report eval Case 3) =================
  # Only a one-line status exists: no burndown, RAID, or chat. The report agent must
  # set insufficient_evidence = true and fabricate nothing. Invisible to the watermelon
  # eval (which hardcodes Atlas/Boreas/Cygnus/Draco).
  - team: Echo
    sprint: 15
    reported_status: green
    insufficient_evidence: true
    divergence_reasons: []
    moat_behaviours: []
    artifacts:
      - { id: status-echo-s15, kind: status, note: "one-line status; no metrics/RAID/chat" }
    expected_evidence: [status-echo-s15]
```

- [ ] **Step 5: Bump the remaining corpus-count couplings to 37**

In `tests/test_ingest.py`, change every `36` that refers to the corpus total to `37` (lines asserting `artifacts_total`, `ingested`, `chunks_written >=`, `counts_after_first["artifact"]`, and `second.skipped`):

```python
    assert first.artifacts_total == 37
    assert first.ingested == 37
    assert first.chunks_written >= 37
    assert counts_after_first["artifact"] == 37
    # ...
    assert second.skipped == 37
```

In `.github/workflows/ci.yml`, update the `db` job (the second-pass idempotency check and the row-count verification):

```yaml
          echo "$out" | grep -q '"skipped": 37' || { echo "EXPECTED 37 SKIPPED"; exit 1; }
```

```yaml
      - name: Verify rows (37 artifacts, chunks embedded)
        run: |
          psql -h localhost -U postgres -d sprintsight -v ON_ERROR_STOP=1 -c "do \$\$
          begin
            if (select count(*) from artifact) <> 37 then
              raise exception 'expected 37 artifacts, got %', (select count(*) from artifact);
```

- [ ] **Step 6: Run the full test suite to verify green**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: PASS — all tests green (watermelon eval unaffected: it still sees exactly Atlas/Boreas/Cygnus/Draco), ruff clean.

- [ ] **Step 7: Commit**

```bash
git add data/corpus/echo/status-echo-s15.md data/ground-truth/labels.yaml tests/test_fixtures.py tests/test_ingest.py .github/workflows/ci.yml
git commit -m "SS-2.A: add Echo thin-data team (report eval Case 3); bump corpus count 36->37"
```

### Task A2: Report contract + audience profiles

**Files:**
- Create: `sprintsight/report/__init__.py` (empty)
- Create: `sprintsight/report/contract.py`
- Create: `sprintsight/report/audience.py`
- Test: `tests/test_report_contract.py`, `tests/test_audience.py`

**Interfaces:**
- Produces: `Claim(text: str, citations: list[str])` (frozen); `Report(team: str, audience: str, sections: dict[str, str], claims: list[Claim], insufficient_evidence: bool)`. `AudienceProfile(name, max_words: int | None, required_sections: tuple[str,...], forbid_ticket_ids: bool, forbid_mechanics: bool)`; `PROFILES: dict[str, AudienceProfile]` keyed `exec`/`programme`/`team`; `TICKET_ID: str` regex; `MECHANICS_TERMS: tuple[str,...]`.

- [ ] **Step 1: Write the contract test**

`tests/test_report_contract.py`:

```python
from sprintsight.report.contract import Claim, Report


def test_report_defaults():
    rep = Report(team="Echo", audience="exec")
    assert rep.sections == {}
    assert rep.claims == []
    assert rep.insufficient_evidence is False


def test_claim_holds_citations():
    c = Claim(text="Velocity 38.", citations=["burndown-boreas-s15"])
    assert c.citations == ["burndown-boreas-s15"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/test_report_contract.py -q`
Expected: FAIL — `ModuleNotFoundError: sprintsight.report.contract`.

- [ ] **Step 3: Create the package marker and contract**

Create empty `sprintsight/report/__init__.py`.

Create `sprintsight/report/contract.py`:

```python
"""The SS-1.5 status-report output contract (report-quality-eval.md §2).

Structured so claims and their citations are machine-extractable by the eval.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Claim:
    """One assertion in a report plus the artifact_ids that support it."""

    text: str
    citations: list[str]


@dataclass
class Report:
    """An audience-tuned status report. `sections` keys vary by audience profile."""

    team: str
    audience: str
    sections: dict[str, str] = field(default_factory=dict)
    claims: list[Claim] = field(default_factory=list)
    insufficient_evidence: bool = False
```

- [ ] **Step 4: Run the contract test to verify it passes**

Run: `.venv/bin/pytest tests/test_report_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Write the audience-profile test**

`tests/test_audience.py`:

```python
import re

from sprintsight.report.audience import MECHANICS_TERMS, PROFILES, TICKET_ID


def test_three_locked_profiles():
    assert set(PROFILES) == {"exec", "programme", "team"}
    assert PROFILES["exec"].max_words == 150
    assert PROFILES["programme"].max_words == 400
    assert PROFILES["team"].max_words is None


def test_exec_forbids_mechanics_and_ids():
    assert PROFILES["exec"].forbid_mechanics is True
    assert PROFILES["exec"].forbid_ticket_ids is True
    assert PROFILES["team"].forbid_mechanics is False


def test_ticket_id_regex_matches_real_ids():
    assert re.search(TICKET_ID, "blocked on DRACO-412 today")
    assert not re.search(TICKET_ID, "all green, nothing to report")
    assert "velocity" in MECHANICS_TERMS
```

- [ ] **Step 6: Run it to verify it fails**

Run: `.venv/bin/pytest tests/test_audience.py -q`
Expected: FAIL — `ModuleNotFoundError: sprintsight.report.audience`.

- [ ] **Step 7: Create the audience profiles**

Create `sprintsight/report/audience.py`:

```python
"""Audience profiles (report-quality-eval.md §4, LOCKED).

Single source of truth for length caps, required section keys, and forbidden detail
markers. Read by both the composer (to shape output) and the eval (to score audience fit).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AudienceProfile:
    name: str
    max_words: int | None  # None = no cap (team)
    required_sections: tuple[str, ...]
    forbid_ticket_ids: bool
    forbid_mechanics: bool  # points / velocity / burndown wording


PROFILES: dict[str, AudienceProfile] = {
    "exec": AudienceProfile(
        "exec", 150, ("overall_rag", "top_risks", "ask"), True, True
    ),
    "programme": AudienceProfile(
        "programme", 400, ("overall_rag", "risks", "dependencies", "milestones"), True, False
    ),
    "team": AudienceProfile(
        "team", None, ("sprint_metrics", "ticket_progress", "blockers"), False, False
    ),
}

# A source-system ticket id, e.g. DRACO-412, ATLAS-12 (two+ leading alphanumerics).
TICKET_ID = r"[A-Z][A-Z0-9]+-\d+"

# Sprint-mechanics wording an exec report must not contain.
MECHANICS_TERMS = ("burndown", "velocity", "story points", "points")
```

- [ ] **Step 8: Run both new test files to verify they pass**

Run: `.venv/bin/pytest tests/test_report_contract.py tests/test_audience.py -q && .venv/bin/ruff check .`
Expected: PASS, ruff clean.

- [ ] **Step 9: Commit**

```bash
git add sprintsight/report/__init__.py sprintsight/report/contract.py sprintsight/report/audience.py tests/test_report_contract.py tests/test_audience.py
git commit -m "SS-2.A: report contract + locked audience profiles"
```

### Task A3: Report eval suite + null writer (lands RED)

**Files:**
- Create: `sprintsight/report/writer.py` (null writer only for now)
- Create: `sprintsight/evals/report.py`
- Create: `scripts/run_report_eval.py`
- Test: `tests/test_report_eval.py`

**Interfaces:**
- Consumes: `Report`, `Claim` (contract); `PROFILES`, `TICKET_ID`, `MECHANICS_TERMS` (audience); `Case`, `Assertion`, `CaseResult`, `SuiteReport`, `run_suite` (harness); `artifacts_for`, `load_ground_truth` (fixtures).
- Produces: `ReportWriter = Callable[[dict[str, Any]], Report]`; `null_writer(inputs) -> Report`; `build_cases() -> list[Case]` (boreas-exec, atlas-programme, echo-thin); `run_report_eval(writer: ReportWriter | None = None) -> SuiteReport` (appends the `audience-triple` case). Assertion dimension names: `citation_coverage`, `citation_validity`, `grounding`, `required_sections`, `audience_fit`, `no_fabrication`, `audience_differentiation`.

- [ ] **Step 1: Write the RED-state test**

`tests/test_report_eval.py`:

```python
from sprintsight.evals.report import build_cases, null_writer, run_report_eval


def test_cases_cover_the_spec():
    names = [c.name for c in build_cases()]
    assert names == ["boreas-exec", "atlas-programme", "echo-thin"]


def test_red_without_a_writer():
    # Eval-first: the null writer abstains, so the suite must not pass.
    report = run_report_eval(null_writer)
    assert report.pass_rate == 0.0
    # The audience-triple case is appended on top of the 3 build_cases().
    assert report.total == 4
    assert "boreas-exec" in report.summary()["failures"]
    assert "audience-triple" in report.summary()["failures"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/test_report_eval.py -q`
Expected: FAIL — `ModuleNotFoundError: sprintsight.evals.report`.

- [ ] **Step 3: Create the null writer**

Create `sprintsight/report/writer.py`:

```python
"""The report-writer seam.

`ReportWriter` is any callable `inputs -> Report`. `null_writer` abstains (eval-first RED
signal). The deterministic `compose` lands in Story B; an Anthropic-backed writer is a later
drop-in behind the same callable (open-wiring item, not built here).
"""

from collections.abc import Callable
from typing import Any

from sprintsight.report.contract import Report

ReportWriter = Callable[[dict[str, Any]], Report]


def null_writer(inputs: dict[str, Any]) -> Report:
    """Abstains: empty report, so every case fails its assertions (RED by design)."""
    return Report(team=inputs["team"], audience=inputs["audience"])
```

- [ ] **Step 4: Create the report eval**

Create `sprintsight/evals/report.py`:

```python
"""Status-report quality eval (SS-1.5).

Implements docs/evals/report-quality-eval.md on the generic harness. Cases are built from
the SS-2.1 corpus fixtures; grounding (assertion C) is checked against the canonical metrics
in data/ground-truth/labels.yaml, independently of how the writer parsed them.

Subject under test: a `ReportWriter` (inputs -> Report). `null_writer` lands RED; the
deterministic `compose` (Story B/C) turns it GREEN.
"""

import re
from collections.abc import Callable
from typing import Any

from sprintsight.evals.fixtures import artifacts_for, load_ground_truth
from sprintsight.evals.harness import Assertion, Case, CaseResult, SuiteReport, run_suite
from sprintsight.report.audience import MECHANICS_TERMS, PROFILES, TICKET_ID, AudienceProfile
from sprintsight.report.contract import Report
from sprintsight.report.writer import ReportWriter, null_writer

JUDGED_SPRINT = 15
Check = Callable[[Report], Assertion]

# (regex over claim text, ground-truth metric key) for numeric grounding (assertion C).
_GROUNDERS = [
    (re.compile(r"committed\s+(\d+)\s+points", re.I), "committed_points"),
    (re.compile(r"completed\s+(\d+)\s+points", re.I), "completed_points"),
    (re.compile(r"carried over\s+(\d+)\s+stor", re.I), "carry_over_stories"),
    (re.compile(r"velocity\s+(\d+)", re.I), "velocity"),
]
_RAG = re.compile(r"overall status[:\s]+(green|amber|red)", re.I)


def _render(rep: Report) -> str:
    return " ".join(list(rep.sections.values()) + [c.text for c in rep.claims])


def _gt_record(team: str, sprint: int = JUDGED_SPRINT) -> dict[str, Any]:
    return next(
        r for r in load_ground_truth()["records"]
        if r["team"] == team and r["sprint"] == sprint
    )


def _coverage() -> Check:  # A
    def check(rep: Report) -> Assertion:
        uncited = [c.text for c in rep.claims if not c.citations]
        return Assertion("citation_coverage", not uncited,
                         f"uncited={uncited}" if uncited else "all claims cited")
    return check


def _validity(valid_ids: set[str]) -> Check:  # B
    def check(rep: Report) -> Assertion:
        bad = [cid for c in rep.claims for cid in c.citations if cid not in valid_ids]
        return Assertion("citation_validity", not bad,
                         f"invalid={bad}" if bad else "all citations valid")
    return check


def _grounding(metrics: dict[str, Any], reported_status: str) -> Check:  # C
    def check(rep: Report) -> Assertion:
        for c in rep.claims:
            for rx, key in _GROUNDERS:
                m = rx.search(c.text)
                if m and int(m.group(1)) != metrics[key]:
                    return Assertion("grounding", False,
                                     f"{key}={m.group(1)} != truth {metrics[key]}")
            rag = _RAG.search(c.text)
            if rag and rag.group(1).lower() != reported_status:
                return Assertion("grounding", False,
                                 f"RAG={rag.group(1).lower()} != reported {reported_status}")
        return Assertion("grounding", True, "numeric/status claims match ground truth")
    return check


def _required_sections(profile: AudienceProfile) -> Check:  # E
    def check(rep: Report) -> Assertion:
        missing = set(profile.required_sections) - set(rep.sections)
        return Assertion("required_sections", not missing,
                         f"missing={sorted(missing)}" if missing else "all sections present")
    return check


def _audience_fit(profile: AudienceProfile) -> Check:  # D
    def check(rep: Report) -> Assertion:
        text = _render(rep)
        words = len(text.split())
        if profile.max_words and words > profile.max_words:
            return Assertion("audience_fit", False, f"{words} words > cap {profile.max_words}")
        if profile.forbid_ticket_ids and re.search(TICKET_ID, text):
            return Assertion("audience_fit", False, "contains ticket id(s)")
        if profile.forbid_mechanics and any(t in text.lower() for t in MECHANICS_TERMS):
            return Assertion("audience_fit", False, "contains sprint mechanics")
        return Assertion("audience_fit", True, f"{words} words, profile respected")
    return check


def _no_fabrication(valid_ids: set[str]) -> Check:  # F
    def check(rep: Report) -> Assertion:
        if not rep.insufficient_evidence:
            return Assertion("no_fabrication", False, "did not flag insufficient evidence")
        bad = [cid for c in rep.claims for cid in c.citations if cid not in valid_ids]
        numeric = [c.text for c in rep.claims if re.search(r"\d", c.text)]
        ok = not bad and not numeric
        return Assertion("no_fabrication", ok,
                         f"invented={bad} numeric={numeric}" if not ok else "no fabrication")
    return check


def build_cases() -> list[Case]:
    """Cases 1-3 of the spec; the audience-triple (Case 4) is appended in run_report_eval."""
    boreas = _gt_record("Boreas")
    atlas = _gt_record("Atlas")
    boreas_ids = set(artifacts_for("Boreas", [JUDGED_SPRINT]))
    atlas_ids = set(artifacts_for("Atlas", [JUDGED_SPRINT]))
    echo_ids = set(artifacts_for("Echo", [JUDGED_SPRINT]))
    return [
        Case(
            "boreas-exec",
            {"team": "Boreas", "audience": "exec",
             "artifacts": artifacts_for("Boreas", [JUDGED_SPRINT])},
            [_coverage(), _validity(boreas_ids),
             _grounding(boreas["metrics"], boreas["reported_status"]),
             _required_sections(PROFILES["exec"]), _audience_fit(PROFILES["exec"])],
        ),
        Case(
            "atlas-programme",
            {"team": "Atlas", "audience": "programme",
             "artifacts": artifacts_for("Atlas", [JUDGED_SPRINT])},
            [_coverage(), _validity(atlas_ids),
             _grounding(atlas["metrics"], atlas["reported_status"]),
             _required_sections(PROFILES["programme"]), _audience_fit(PROFILES["programme"])],
        ),
        Case(
            "echo-thin",
            {"team": "Echo", "audience": "exec",
             "artifacts": artifacts_for("Echo", [JUDGED_SPRINT])},
            [_no_fabrication(echo_ids)],
        ),
    ]


def _audience_triple(writer: ReportWriter) -> CaseResult:
    """Case 4: same Boreas s15 across exec/programme/team must differentiate."""
    arts = artifacts_for("Boreas", [JUDGED_SPRINT])
    rendered = {
        aud: _render(writer({"team": "Boreas", "audience": aud, "artifacts": arts}))
        for aud in ("exec", "programme", "team")
    }
    we, wp, wt = (len(rendered[a].split()) for a in ("exec", "programme", "team"))
    distinct = len(set(rendered.values())) == 3
    exec_clean = not any(t in rendered["exec"].lower() for t in MECHANICS_TERMS)
    team_granular = "points" in rendered["team"].lower()
    ok = distinct and we < wp and we < wt and exec_clean and team_granular
    detail = (f"words exec={we} prog={wp} team={wt}; distinct={distinct} "
              f"exec_clean={exec_clean} team_granular={team_granular}")
    return CaseResult("audience-triple", ok, [Assertion("audience_differentiation", ok, detail)])


def run_report_eval(writer: ReportWriter | None = None) -> SuiteReport:
    """Run the report suite; default writer is the abstaining null writer (RED)."""
    writer = writer or null_writer
    report = run_suite(build_cases(), writer)
    report.results.append(_audience_triple(writer))
    return report
```

- [ ] **Step 5: Run the eval test to verify RED**

Run: `.venv/bin/pytest tests/test_report_eval.py -q`
Expected: PASS — the test asserts the suite is correctly RED (pass_rate 0.0, 4 cases).

- [ ] **Step 6: Create the scoreboard script**

Create `scripts/run_report_eval.py`:

```python
"""Run the report-quality eval (SS-1.5) and print the scoreboard.

    .venv/bin/python scripts/run_report_eval.py

Pre-composer this reports RED by design. Once `compose` is wired it goes GREEN. Exits
non-zero unless fully green, so it doubles as the CI eval gate.
"""

import json
import sys

from sprintsight.evals.report import run_report_eval


def main() -> int:
    report = run_report_eval()  # default null writer until Story B wires `compose`
    print(json.dumps(report.summary(), indent=2))
    print("\nPer-case:")
    for r in report.results:
        verdict = "PASS" if r.passed else "FAIL"
        checks = ", ".join(f"{a.name}={'ok' if a.passed else 'x'}" for a in r.assertions)
        print(f"  {r.name:16} {verdict}  [{checks}]")
        if r.error:
            print(f"                   error: {r.error}")
    return 0 if report.pass_rate == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Verify the script reports RED (non-zero exit)**

Run: `.venv/bin/python scripts/run_report_eval.py; echo "exit=$?"`
Expected: scoreboard prints, `pass_rate` 0.0, `exit=1`.

- [ ] **Step 8: Full suite + lint**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: PASS, ruff clean.

- [ ] **Step 9: Commit**

```bash
git add sprintsight/report/writer.py sprintsight/evals/report.py scripts/run_report_eval.py tests/test_report_eval.py
git commit -m "SS-2.A: report-quality eval (SS-1.5) on the harness — RED with null writer"
```

---

# STORY B — Deterministic composer turns citation + grounding green

Deliverable: `compose` produces cited, grounded, audience-shaped reports so the `citation_coverage`, `citation_validity`, `grounding`, and `required_sections` dimensions pass for boreas-exec and atlas-programme. (`audience_fit` length/forbidden-marker tightening and the fabrication/differentiation gates are Story C.)

### Task B1: Metric, RAG, and risk/dependency extraction helpers

**Files:**
- Modify: `sprintsight/report/writer.py`
- Test: `tests/test_report_writer.py`

**Interfaces:**
- Consumes: `parse_metrics`, `parse_reported_status` from `sprintsight.detector`; `Artifact` via inputs.
- Produces (module-internal): `_metric_claims(metrics, burndown_id) -> list[Claim]`; `_rag_claim(rag, cite) -> Claim`; `_risk_lines(arts, raid_id) -> list[str]`; `_dependency_lines(arts, raid_id) -> list[str]`. Each returned claim text uses the canonical phrasings the eval's `_GROUNDERS`/`_RAG` recognise: `"Committed N points."`, `"Completed N points."`, `"Carried over N stories."`, `"Velocity N."`, `"Overall status: <rag>."`.

- [ ] **Step 1: Write helper tests**

`tests/test_report_writer.py`:

```python
from sprintsight.evals.fixtures import artifacts_for
from sprintsight.report.writer import _dependency_lines, _metric_claims, _risk_lines
from sprintsight.detector import parse_metrics


def test_metric_claims_use_canonical_phrasing():
    arts = artifacts_for("Boreas", [15])
    m = parse_metrics(arts["burndown-boreas-s15"].body)
    texts = [c.text for c in _metric_claims(m, "burndown-boreas-s15")]
    assert "Committed 40 points." in texts
    assert "Completed 38 points." in texts
    assert "Carried over 1 stories." in texts
    assert "Velocity 38." in texts
    for c in _metric_claims(m, "burndown-boreas-s15"):
        assert c.citations == ["burndown-boreas-s15"]


def test_risk_lines_read_the_raid_descriptions_only():
    arts = artifacts_for("Atlas", [15])
    risks = _risk_lines(arts, "raid-atlas-s15")
    assert any("leave" in r.lower() for r in risks)
    # Risk text is the description column, never the R-A15-1 id column.
    assert all("R-A15-1" not in r for r in risks)


def test_dependency_lines_from_raid():
    arts = artifacts_for("Atlas", [15])
    deps = _dependency_lines(arts, "raid-atlas-s15")
    assert any("design system" in d.lower() for d in deps)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_report_writer.py -q`
Expected: FAIL — helpers not defined (`ImportError`).

- [ ] **Step 3: Implement the helpers**

Add to `sprintsight/report/writer.py` (update the imports at the top, then append the helpers):

```python
import re

from sprintsight.detector import Metrics, parse_metrics, parse_reported_status
from sprintsight.evals.fixtures import Artifact
from sprintsight.report.contract import Claim, Report


def _metric_claims(m: Metrics, burndown_id: str) -> list[Claim]:
    return [
        Claim(f"Committed {int(m.committed)} points.", [burndown_id]),
        Claim(f"Completed {int(m.completed)} points.", [burndown_id]),
        Claim(f"Carried over {int(m.carry_over)} stories.", [burndown_id]),
        Claim(f"Velocity {int(m.velocity)}.", [burndown_id]),
    ]


def _rag_claim(rag: str, cite: str) -> Claim:
    return Claim(f"Overall status: {rag}.", [cite])


def _table_descriptions(body: str, heading: str) -> list[str]:
    """Second-column cells of the markdown table under `## <heading>` (skips id + header)."""
    out: list[str] = []
    in_section = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower() == f"## {heading.lower()}"
            continue
        if in_section and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 2 or set(cells[1]) <= {"-"} or cells[1].lower() in {"risk", "dependency"}:
                continue  # separator or header row
            out.append(cells[1])
    return out


def _risk_lines(arts: dict[str, Artifact], raid_id: str) -> list[str]:
    if raid_id not in arts:
        return []
    return _table_descriptions(arts[raid_id].body, "Risks")


def _dependency_lines(arts: dict[str, Artifact], raid_id: str) -> list[str]:
    if raid_id not in arts:
        return []
    return _table_descriptions(arts[raid_id].body, "Dependencies")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_report_writer.py -q && .venv/bin/ruff check .`
Expected: PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add sprintsight/report/writer.py tests/test_report_writer.py
git commit -m "SS-2.B: metric/RAG/risk/dependency extraction helpers (reuse detector parsers)"
```

### Task B2: The `compose` writer — cited, grounded, sectioned reports

**Files:**
- Modify: `sprintsight/report/writer.py`
- Modify: `tests/test_report_writer.py`
- Test: `tests/test_report_eval.py` (add a per-dimension green test)

**Interfaces:**
- Produces: `compose(inputs: dict[str, Any]) -> Report` — a `ReportWriter`. Emits a RAG claim for all audiences; metric claims for programme/team; risk/dependency/milestone/blocker sections per profile; sets `insufficient_evidence=True` and emits no claims when no burndown artifact exists for the team's sprint.

- [ ] **Step 1: Add the compose dimension test to the eval test file**

Append to `tests/test_report_eval.py`:

```python
from sprintsight.report.writer import compose


def test_compose_greens_citation_and_grounding():
    report = run_report_eval(compose)
    dims = report.dimension_rates()
    # Every claim cited, every citation valid, every numeric/status claim grounded.
    assert dims["citation_coverage"][0] == dims["citation_coverage"][1]
    assert dims["citation_validity"][0] == dims["citation_validity"][1]
    assert dims["grounding"][0] == dims["grounding"][1]
    # Required sections present for both audience cases.
    assert dims["required_sections"] == (2, 2)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_report_eval.py::test_compose_greens_citation_and_grounding -q`
Expected: FAIL — `compose` not defined (`ImportError`).

- [ ] **Step 3: Implement `compose`**

Append to `sprintsight/report/writer.py`:

```python
from sprintsight.report.audience import PROFILES


def _looking_ahead(arts: dict[str, Artifact], status_id: str) -> str:
    """A milestones blurb pulled from the status report's forward-looking prose (no ids)."""
    if status_id not in arts:
        return "Sprint 16 planning underway."
    for line in arts[status_id].body.splitlines():
        low = line.lower()
        if "sprint 16" in low and not re.search(r"[A-Z][A-Z0-9]+-\d+", line):
            return line.strip()
    return "Sprint 16 planning underway."


def compose(inputs: dict[str, Any]) -> Report:
    """Deterministic, audience-tuned, fully-cited report writer (the SS-1.5 subject)."""
    team: str = inputs["team"]
    audience: str = inputs["audience"]
    arts: dict[str, Artifact] = inputs["artifacts"]
    profile = PROFILES[audience]
    t = team.lower()
    burndown_id = f"burndown-{t}-s15"
    status_id = f"status-{t}-s15"
    raid_id = f"raid-{t}-s15"

    # Thin-data guard (fabrication gate): no burndown -> nothing to substantiate.
    if burndown_id not in arts:
        return Report(team=team, audience=audience, insufficient_evidence=True)

    metrics = parse_metrics(arts[burndown_id].body)
    rag = parse_reported_status(arts[status_id].body) if status_id in arts else "green"
    rag_cite = status_id if status_id in arts else burndown_id
    risks = _risk_lines(arts, raid_id)
    deps = _dependency_lines(arts, raid_id)

    claims = [_rag_claim(rag, rag_cite)]
    sections: dict[str, str] = {}

    if profile.name == "exec":
        sections["overall_rag"] = f"Overall delivery status is {rag}."
        top = risks[:3]
        sections["top_risks"] = " ".join(top) if top else "No material risks reported."
        sections["ask"] = "Decision needed: none this period."
        claims += [Claim(r, [raid_id]) for r in top]
    elif profile.name == "programme":
        claims += _metric_claims(metrics, burndown_id)
        sections["overall_rag"] = f"Delivery status {rag}."
        sections["risks"] = " ".join(risks) if risks else "No risks logged."
        sections["dependencies"] = " ".join(deps) if deps else "No external dependencies logged."
        sections["milestones"] = _looking_ahead(arts, status_id)
        claims += [Claim(r, [raid_id]) for r in risks]
    else:  # team — most granular, no caps, all detail
        claims += _metric_claims(metrics, burndown_id)
        sections["sprint_metrics"] = (
            f"Committed {int(metrics.committed)} points, "
            f"completed {int(metrics.completed)} points, "
            f"velocity {int(metrics.velocity)}, "
            f"{int(metrics.carry_over)} stories carried over."
        )
        sections["ticket_progress"] = (
            "Stories progressed across the sprint; carry-over items remain in flight."
        )
        sections["blockers"] = " ".join(risks) if risks else "No blockers reported."
        claims += [Claim(r, [raid_id]) for r in risks]

    return Report(team=team, audience=audience, sections=sections, claims=claims)
```

- [ ] **Step 4: Run the dimension test to verify it passes**

Run: `.venv/bin/pytest tests/test_report_eval.py::test_compose_greens_citation_and_grounding -q`
Expected: PASS.

- [ ] **Step 5: Full suite + lint**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: PASS, ruff clean. (`test_red_without_a_writer` still passes — it pins the null writer, not `compose`.)

- [ ] **Step 6: Commit**

```bash
git add sprintsight/report/writer.py tests/test_report_writer.py tests/test_report_eval.py
git commit -m "SS-2.B: deterministic compose writer — citation coverage/validity + grounding green"
```

---

# STORY C — Audience tuning + fabrication gate → eval fully GREEN

Deliverable: every dimension passes — `audience_fit` (length caps + forbidden markers), `no_fabrication` (Echo), and `audience_differentiation` — so `run_report_eval(compose).pass_rate == 1.0`. The script becomes a CI gate.

### Task C1: Audience-fit + fabrication + differentiation green

**Files:**
- Modify: `tests/test_report_eval.py`
- Modify: `sprintsight/report/writer.py` (only if a fit check fails — see Step 2)
- Test: `tests/test_report_eval.py`

**Interfaces:**
- Consumes: `compose`, `run_report_eval`.
- Produces: a passing full-suite assertion. No new public API.

- [ ] **Step 1: Write the fully-green test**

Append to `tests/test_report_eval.py`:

```python
def test_compose_greens_the_whole_suite():
    report = run_report_eval(compose)
    assert report.pass_rate == 1.0, report.summary()
    dims = report.dimension_rates()
    assert dims["audience_fit"] == (2, 2)
    assert dims["no_fabrication"] == (1, 1)
    assert dims["audience_differentiation"] == (1, 1)


def test_echo_triggers_insufficient_evidence():
    from sprintsight.evals.fixtures import artifacts_for
    rep = compose({"team": "Echo", "audience": "exec",
                   "artifacts": artifacts_for("Echo", [15])})
    assert rep.insufficient_evidence is True
    assert rep.claims == []
```

- [ ] **Step 2: Run it; diagnose any failing dimension**

Run: `.venv/bin/python scripts/run_report_eval.py; echo "exit=$?"`
Expected (target): scoreboard shows all 4 cases PASS, `pass_rate` 1.0, `exit=0`.

If the scoreboard shows a failing dimension, fix it deterministically against its `detail` message, then re-run:
- `audience_fit` exec "too long": the exec sections/claims exceed 150 words — trim the `ask`/`top_risks` wording in `compose`.
- `audience_fit` "contains sprint mechanics": an exec section/claim contains `points`/`velocity` — exec must not include metric claims (confirm the `elif/else` guards keep `_metric_claims` out of the exec branch).
- `audience_fit` "contains ticket id(s)": a risk/dependency description carried an id — confirm `_table_descriptions` returns the description column only.
- `audience_differentiation` `we < wp`/`we < wt` false: exec is not shortest — confirm exec omits metric claims and the team branch includes them.

Do NOT loosen an assertion to pass; fix the composer output.

- [ ] **Step 3: Run the full pytest suite + lint**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: PASS — including `test_compose_greens_the_whole_suite` and `test_echo_triggers_insufficient_evidence`; ruff clean.

- [ ] **Step 4: Commit**

```bash
git add sprintsight/report/writer.py tests/test_report_eval.py
git commit -m "SS-2.C: audience fit + fabrication gate + differentiation — report eval fully GREEN"
```

### Task C2: Wire the report eval into CI + update state docs

**Files:**
- Modify: `.github/workflows/ci.yml` (add a gate step to `lint-and-test`)
- Modify: `HANDOVER.md`
- Test: CI run on push

**Interfaces:** none (CI + docs).

- [ ] **Step 1: Add the eval gate to the `lint-and-test` job**

In `.github/workflows/ci.yml`, after the `Test (pytest)` step, add:

```yaml
      - name: Report-quality eval (SS-1.5) must be green
        run: python scripts/run_report_eval.py
```

- [ ] **Step 2: Verify the gate locally (mirrors CI)**

Run: `.venv/bin/python scripts/run_report_eval.py; echo "exit=$?"`
Expected: `exit=0`.

- [ ] **Step 3: Update HANDOVER.md**

In `HANDOVER.md`, update the "Where we are" section to record Stage 2 progress: report eval green (4/4 cases), Echo thin-data team added (corpus now 37), the report-writer composer behind the `ReportWriter` seam, LLM drop-in still deferred (open-wiring). Note the report eval now gates `lint-and-test`.

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/ci.yml HANDOVER.md
git commit -m "SS-2.C: gate CI on the report eval; HANDOVER -> Stage 2 report agent green"
git push
```

- [ ] **Step 5: Confirm CI green**

Run: `gh run list --branch main --limit 1`
Expected: latest run for the push is `completed`/`success` on both `lint-and-test` (now incl. the report-eval gate) and `db` (now 37 artifacts).

---

## Self-Review (completed during planning)

**Spec coverage** (docs/evals/report-quality-eval.md):
- §2 contract → Task A2 (`Report`/`Claim`). §3 assertions A–F → `sprintsight/evals/report.py` (`_coverage`/`_validity`/`_grounding`/`_required_sections`/`_audience_fit`/`_no_fabrication`), Tasks A3–C1.
- §4 audience profiles → Task A2 (`PROFILES`). §5 cases 1–4 → `build_cases` + `_audience_triple` (A3); composer behaviour B2/C1. §6 hard gate (Case 3) → `_no_fabrication` + thin-data guard (B2). §7 scoring → reused harness `summary()`/`dimension_rates()`. §10 pass bar → `test_compose_greens_the_whole_suite`.

**Scope note (deliberate, consistent with ADR-0001):** the composer represents *structured* artifacts (status/burndown/RAID). Surfacing the chat-only Draco dependency into Atlas's report is the **risk/reconciliation node's** job (Stage 3), not the report writer — so it is out of scope here. Case 2's assertions (A,B,C,D-programme,E) are satisfied without it; the dependencies section is sourced from the RAID. This matches design-doc §10 (LangGraph/risk-node wiring deferred).

**Placeholder scan:** none — every step has concrete code/commands/expected output.

**Type consistency:** `Report`/`Claim` fields, `compose`/`null_writer` signatures (`dict[str, Any] -> Report`), `ReportWriter` alias, assertion dimension names (`citation_coverage`/`citation_validity`/`grounding`/`required_sections`/`audience_fit`/`no_fabrication`/`audience_differentiation`), and the canonical claim phrasings vs `_GROUNDERS`/`_RAG` regexes are consistent across the eval and the writer.
