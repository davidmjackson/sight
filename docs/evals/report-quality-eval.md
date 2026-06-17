# Sprintsight — Eval Spec: Status Report Quality (SS-1.5)

Status: LOCKED 2026-06-17 (audience profiles confirmed). Satisfies SS-1.5. Paper spec, no code.
Depends on SS-1.3 roster. Same structure as SS-1.4. Feeds Stage 2 (status report agent).
Repo path: docs/evals/report-quality-eval.md

## 1. What this tests
The status-report agent takes one team's artifacts plus a target audience and produces
an audience-tuned report where every claim is cited to a source. Report quality is
subjective, so this eval scores OBJECTIVE, checkable properties only: citation,
grounding, audience fit, and refusal to fabricate. It does not score prose style.

## 2. Report agent contract (interface under test)
Input: a team's artifacts for a sprint, plus audience in {team, programme, exec}.
Output (structured JSON so claims and citations are machine-extractable):
```json
{
  "team": "Boreas",
  "audience": "exec",
  "sections": { "summary": "...", "risks": "...", "next": "..." },
  "claims": [
    { "text": "Sprint 15 burned 38 of 40 committed points.", "citations": ["burndown-boreas-s15"] }
  ],
  "insufficient_evidence": false
}
```

## 3. Assertions (the objective checks)
- A. Citation coverage: every claim in `claims` has at least one citation. Zero uncited claims.
- B. Citation validity: every cited artifact_id exists in the input set. No invented sources.
- C. Factual grounding (deterministic subset): every numeric or status claim (points, velocity, RAG, dates) matches the source artifact it cites. Mismatch = fail.
- D. Audience fit: the report matches the target audience profile (section 4).
- E. Required sections present for that audience (section 4).
- F. No fabrication: on thin input, the agent sets insufficient_evidence = true and does NOT emit uncited or unsupported claims.

## 4. Audience profiles (LOCKED)
These are the product decision. Confirmed defaults:

| Audience | Length cap | Detail level | Required sections | Must NOT contain |
|----------|-----------|--------------|-------------------|------------------|
| exec | ~150 words | Outcome and risk only | overall RAG, top 3 risks, ask/decision needed | ticket IDs, sprint mechanics |
| programme | ~400 words | Roll-up plus governance | RAG, risks, dependencies, milestones | individual ticket churn |
| team | no cap | Granular | sprint metrics, ticket-level progress, blockers | n/a |

Audience fit is checked by: section presence, length bound, and detail markers
(for example, presence/absence of ticket IDs and burndown numbers).

## 5. Cases
### Case 1 - Boreas, exec (happy path, clean green data)
- Assert A, B, C, D (exec profile), E. Short, outcome-level, fully cited.

### Case 2 - Atlas, programme (rich data, the watermelon team)
- Assert A, B, C, D (programme profile), E. The report must faithfully represent the
  underlying data with citations, including the dependency and flat burndown.
- Note: judging whether Atlas IS a watermelon is the SS-1.4 detector's job, not this eval.
  Here we only test faithful, cited, audience-tuned representation.

### Case 3 - Thin-data TRAP (fabrication guard)
- Input: a team with only a one-line status and no metrics, RAID, or chat.
- Expected: insufficient_evidence = true, no fabricated burndown/velocity/risk claims.
- Any invented claim or any claim citing a nonexistent artifact = FAIL. This is the hard gate.

### Case 4 - Audience triple (differentiation)
- Same input (Boreas s15) generated for team, programme, exec.
- Assert exec is shortest and highest-level, team is most granular, each meets its profile.
- Fail if two audiences produce substantially the same report.

## 6. Pass criteria
A case passes only when ALL its asserted checks (A-F as applicable) hold.
Case 3 (fabrication) is a hard gate: any fabrication fails the whole suite run.

## 7. Scoring
Per suite run, report:
- Citation coverage: percent of claims cited, across all cases (target 100 percent).
- Citation validity: percent of citations pointing to real artifacts (target 100 percent).
- Grounding accuracy: percent of numeric/status claims matching source (target 100 percent).
- Audience-fit pass rate: cases meeting their profile, out of 4.
- Fabrication gate: pass/fail (Case 3).

## 8. Grading method
Deterministic-first, consistent with SS-1.4:
- A, B, E, F: structural checks in code.
- C: deterministic for numeric/status claims (compare to source).
- D: deterministic via section presence, length bounds, detail markers.
- Fuzzy prose grounding and tone quality: optional LLM-as-judge, NOT a gate, deferred to Stage 4.

## 9. Failure modes this catches
- Uncited claim (assertion without a source).
- Invented source (citation to an artifact that does not exist).
- Wrong number (claim says 38 points, source says 12).
- Audience bleed (exec report dumps ticket detail; or all three audiences look the same).
- Fabrication on thin data (the worst case, hard gate).

## 10. Showcase pass bar
Target on a credible run: 100 percent citation coverage and validity, 100 percent
grounding on numeric claims, 4/4 audience fit, fabrication gate passed. Misses are
documented with the failing case, same as SS-1.4.

## 11. What this unblocks
- Stage 2 status report agent has a concrete target.
- The report contract (section 2) pre-shapes the Stage 2 build.
- Together with SS-1.4, Foundation's two eval specs are complete.
