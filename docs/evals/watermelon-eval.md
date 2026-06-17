# Sprintsight — Eval Spec: Watermelon Detection (SS-1.4)

Status: LOCKED 2026-06-17 (deterministic grading confirmed). Satisfies SS-1.4. Paper spec, no code.
Depends on SS-1.3 roster. Feeds Stage 1 (the harness implements this).
Repo path: docs/evals/watermelon-eval.md

## 1. What this tests
Given one team's artifacts for Sprints 14 to 15, the detector must judge whether the
team is a watermelon (reported healthier than reality) and back the judgement with
the specific evidence that proves it. The eval scores both the verdict and the evidence.

## 2. Detector contract (interface under test)
Input: all artifacts for a single team across Sprints 14 and 15 (status reports, RAID, ticket/burndown summary, chat).
Output (structured JSON):
```json
{
  "team": "Atlas",
  "reported_status": "green",
  "actual_status": "red",
  "is_watermelon": true,
  "evidence": ["slack-atlas-s15-msg-dep", "burndown-atlas-s15", "status-atlas-s15"],
  "explanation": "Short prose: why reported and actual diverge."
}
```
The eval compares this against the ground-truth labels from the data strategy.

## 3. Cases (one per team, judged as-of Sprint 15 with Sprint 14 as context)

### Case 1 — Atlas (TRUE WATERMELON)
- Expected: is_watermelon = true, actual_status = red, reported_status = green.
- Required evidence (all must be cited):
  - burndown-atlas-s15  (flat burndown across two sprints)
  - slack-atlas-s15-msg-dep  (the Draco auth dependency raised in chat, absent from RAID)
  - status-atlas-s15  (the "on track" claim that contradicts the data)
- This is the case that must never be missed. A false negative here is the worst failure.

### Case 2 — Boreas (TRUE GREEN)
- Expected: is_watermelon = false, actual_status = green, reported_status = green.
- Required evidence (all must be cited):
  - burndown-boreas-s15  (tracking to plan)
  - raid-boreas-s15  (current, owned, mitigated)
- Must NOT be flagged. A false positive here is a precision failure.

### Case 3 — Cygnus (HONEST AMBER)
- Expected: is_watermelon = false, actual_status = amber, reported_status = amber.
- Required evidence (all must be cited):
  - status-cygnus-s15  (openly reports amber and the slip)
  - raid-cygnus-s15  (same slip logged honestly)
- Tests that reported-amber-and-actually-amber is NOT a watermelon. The detector must
  compare reported vs actual, not just react to a negative signal.

### Case 4 — Draco (TRICKY NEAR-MISS)
- Expected: is_watermelon = false, actual_status = amber, reported_status = green-then-amber.
- Required evidence (all must be cited):
  - bugspike-draco-s15  (the alarming signal)
  - triage-draco-s15  (evidence it is under control: triaged, burndown still OK, risk logged)
- The decoy case. A scary signal that resolves to amber. The detector must resist
  calling it a watermelon. Guards precision under pressure.

(Expansion later: add Sprint-14-only variants to test point-in-time vs trend judgement.)

## 4. Pass criteria (per case)
A case PASSES only when BOTH hold:
1. Classification match: is_watermelon AND actual_status equal the ground truth.
2. Evidence match: every artifact_id in that case's required-evidence list appears in the output's evidence array.

Right label with missing evidence = FAIL. This is deliberate. It blocks lucky guesses.

## 5. Scoring
Per suite run, report three numbers:
- Classification accuracy: cases with correct is_watermelon and actual_status, out of 4.
- Evidence accuracy: cases citing all required evidence, out of 4.
- Overall pass rate: cases passing BOTH gates, out of 4.

## 6. Grading method
- Primary, deterministic (LOCKED): assert classification equality and evidence set-membership in code. Objective, reproducible, cheap. This is the credible core and the eval-first signal.
- Secondary, optional, LLM-as-judge: score explanation coherence 1 to 5. A soft metric, NOT a pass gate. Defer to Stage 4 (Observability + Evals hardening). Subjective, so it never decides pass or fail.

Decision (LOCKED): deterministic-only for the showcase. The LLM-judge layer is deferred to Stage 4 (Observability + Evals hardening).

## 7. Failure modes this catches
- False negative on Atlas (misses the watermelon). Worst case.
- False positive on Boreas (flags a healthy team). Precision failure.
- Over-flagging Cygnus (mistakes honest amber for a watermelon).
- Tripped by the Draco decoy (scary signal -> false watermelon).
- Lucky guess (right label, no evidence) -> fails the evidence gate.

## 8. Showcase pass bar
Target on a credible run: 4/4 classification AND 4/4 evidence. Any miss is documented
in the eval results with the failing case and the reasoning gap, which is itself good
showcase material (shows the eval is real and bites).

## 9. What this unblocks
- Stage 1 harness has a concrete target to implement.
- The detector's output contract (section 2) pre-shapes the Stage 1 / Stage 6 build.
- SS-1.5 (report eval) follows the same structure for status reports.
