# Stage 2 Design — Status Report Agent (Epic SS-1)

Status: APPROVED 2026-06-18 (brainstorming sign-off). Drives the Stage-2 build.
Implements the locked eval spec docs/evals/report-quality-eval.md (SS-1.5) and the
report-writer node from docs/adr/ADR-0001-three-agent-graph.md.

Read alongside: HANDOVER.md (state), CLAUDE.md (build conventions), docs/evals/report-quality-eval.md
(the eval contract this builds to), data/ground-truth/labels.yaml (canonical metrics).

## 1. Goal & guardrails
Build the Stage-2 status-report agent: given one team's artifacts for a sprint plus a target
audience, produce an audience-tuned, fully-cited status report that refuses to fabricate on thin
data. Eval-first throughout: the SS-1.5 report eval lands RED before any agent code, then the
agent turns it GREEN. Deterministic, no network, ZDR-clean — runs in CI with no Anthropic key.

## 2. Decisions locked in brainstorming (2026-06-18)
1. **Deterministic composer + LLM seam.** The subject under test is a deterministic
   `DeterministicComposer` that turns the eval green in CI. The real Anthropic-backed writer is a
   deferred drop-in behind the same `ReportWriter` interface — consistent with the Stage-1
   stand-ins (HashingEmbedder, deterministic detector). The eval grades objective properties only
   (citation, grounding, audience fit, fabrication refusal); fuzzy prose/tone is deferred to a
   Stage-4 LLM judge, so nothing the eval gates on needs the LLM yet.
2. **Thin-data trap = a real 5th corpus team, "Echo".** Case 3 (fabrication guard) needs a team
   with only a one-line status and no metrics/RAID/chat. No existing team qualifies, so Echo joins
   the corpus as a first-class citizen (one artifact + a sparse ground-truth record), exercising
   the genuine loader path rather than an inline eval-only fixture. Invisible to the watermelon
   eval, which hardcodes `TEAMS = [Atlas, Boreas, Cygnus, Draco]`.
3. **Grounding checked against ground truth, not re-parsed artifacts.** The composer reads only the
   artifacts (never ground truth — that would cheat). The eval's grounding assertion validates
   numeric claims against `data/ground-truth/labels.yaml` canonical metrics, independently of how
   the composer parsed them. Composer reads artifact bodies; eval checks against hand-authored
   truth — the independence is what gives assertion C real teeth.

## 3. Components
New package `sprintsight/report/`, plus the eval beside the existing ones:

- **`sprintsight/report/contract.py`** — the SS-1.5 §2 output contract as frozen dataclasses:
  `Claim(text: str, citations: list[str])` and
  `Report(team, audience, sections: {summary, risks, next}, claims: list[Claim], insufficient_evidence: bool)`.
- **`sprintsight/report/audience.py`** — the three LOCKED audience profiles (exec / programme /
  team) as data: length cap, required sections, forbidden detail-markers (ticket IDs, burndown
  numbers). One source of truth, read by both composer and eval.
- **`sprintsight/report/writer.py`** — `ReportWriter` Protocol (the seam) + `DeterministicComposer`.
  The LLM-backed writer is a deferred drop-in behind the same Protocol (open-wiring item).
- **`sprintsight/evals/report.py`** — mirrors `watermelon.py`: `build_cases()` from corpus fixtures
  + ground truth, assertions A–F, `run_report_eval(writer=None)` defaulting to a `null_writer` that
  lands RED.
- **`scripts/run_report_eval.py`** — entrypoint, exits non-zero on failure (mirrors
  `run_watermelon_eval.py`); added to CI.
- **`data/corpus/echo/status-echo-s15.md`** — the thin 5th team + a sparse `labels.yaml` record
  (insufficient-evidence case).

## 4. Data flow
`build_cases()` → for each (team, audience) case:
`inputs = {team, audience, artifacts: artifacts_for(team, [15])}` →
`DeterministicComposer.write(inputs)` → `Report` → assertions A–F score it.
The composer reads only the artifacts. The grounding assertion (C) validates numeric claims against
`labels.yaml`. Composer reads artifact bodies; eval checks against hand-authored truth — independent
by construction.

## 5. The deterministic composer
Extracts the canonical metric line (`Committed/Completed/Carry-over/Velocity`, present in burndown
and status artifact bodies) via a fixed parse, emits one cited `Claim` per metric (citation = the
artifact_id it parsed), pulls overall RAG from the status artifact, and risks/dependencies from RAID
+ chat artifacts. Audience shaping = profile-driven filtering: exec gets RAG + top-3 risks + ask, no
ticket IDs/mechanics; team gets everything. If the required source artifacts are absent (Echo), it
emits zero metric claims and sets `insufficient_evidence = true` — the fabrication gate passing by
construction.

## 6. The eval (assertions A–F, from docs/evals/report-quality-eval.md §3)
- A. Citation coverage: every claim has ≥1 citation. Structural.
- B. Citation validity: every cited artifact_id exists in the input set. Structural.
- C. Factual grounding: every numeric/status claim matches the canonical metric in `labels.yaml`.
- D. Audience fit: section presence + length bound + detail-marker presence/absence, per profile.
- E. Required sections present for the audience.
- F. No fabrication: on thin input, `insufficient_evidence = true` and no uncited/unsupported claims.

Per-dimension scoring reuses the harness `dimension_rates()` (assertion name = dimension). Case 3 is
a hard gate: any fabrication fails the suite run.

## 7. Cases (spec §5)
1. **Boreas exec** — happy path; A, B, C, D-exec, E. Short, outcome-level, fully cited.
2. **Atlas programme** — faithful cited representation incl. the dependency + flat burndown; A, B,
   C, D-programme, E. (Whether Atlas IS a watermelon is the SS-1.4 detector's job, not this eval.)
3. **Echo thin-data trap** — `insufficient_evidence = true`, zero fabricated claims (hard gate F).
4. **Audience triple** — same Boreas s15 as team/programme/exec; assert exec shortest & highest
   level, team most granular, each meets its profile; fail if two audiences are substantially
   identical.

## 8. Testing / CI
Report eval runs in the `lint-and-test` job via `run_report_eval.py` (deterministic, no key, no
network). Plus unit tests on the composer's metric parse and the audience-profile filters. Eval
lands RED on Story A (null writer), goes GREEN on Stories B–C.

## 9. Stories (eval-first), under Epic SS-1
- **Story A** — Echo thin fixture + report eval (A–F) implemented, lands RED (null writer).
- **Story B** — `DeterministicComposer` + `ReportWriter` seam → citation coverage/validity +
  grounding green.
- **Story C** — audience profiles (exec/programme/team) + fabrication gate → audience-fit + Case 3
  green; eval fully GREEN.

Each walked one-status-at-a-time to Done with AC-check comments, per docs/jira/workflow.md.

## 10. Out of scope / deferred (YAGNI)
- LLM-backed report writer (drop-in behind `ReportWriter` once the Anthropic key is wired).
- LLM-as-judge for prose/tone quality (Stage 4).
- Portfolio/watermelon UI (Stage 6).
- LangGraph node wiring (Stage 3+); the composer stays a function/class until evals justify
  promotion (ADR-0001).
