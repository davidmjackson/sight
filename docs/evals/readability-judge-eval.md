# Sprintsight Eval Spec: Readability Judge (SS-7)

Status: ACTIVE 2026-06-19 (advisory; not yet a build gate). Satisfies SS-7 (Stage 4).
Depends on SS-1.5 (report contract). Code: sprintsight/evals/judge.py.
Repo path: docs/evals/readability-judge-eval.md

## 1. What this tests

The deterministic report-quality eval (SS-1.5) checks objective properties: citation
coverage, grounding accuracy, section presence, and audience fit by structural markers.
What it cannot measure is prose quality. A report can cite everything correctly and still
read like a wall of jargon, feel written for the wrong person, or leave the reader unsure
what to do next.

This eval fills that gap. Given a finished status Report, the judge scores four prose
dimensions from 1 (poor) to 5 (excellent) using an LLM grader. It is PROSE ONLY: no
re-checking of citations, numbers, or section presence.

## 2. Interface under test

Input: a `Report` (team, audience, sections dict) and the target audience string.
Output: a `JudgeScore` with:
- `scores`: one integer (1 to 5) per dimension.
- `reasons`: one short string per dimension explaining the score.
- `mean`: average score across all four dimensions.
- `passes`: True only when every dimension is at least 3 AND the mean is at least 4.0.

## 3. The four dimensions

| Dimension | What the judge looks for |
|---|---|
| clarity | Plain English, low jargon, readable by a non-engineer |
| audience_fit | Register matches the audience (exec = outcomes and decisions, team = granular detail) |
| coherence | One joined-up narrative, no repetition, reads as a whole not a list |
| actionability | The ask or decision-needed is specific; the reader knows what to do next |

The 1-to-5 scale:
- 5: Exemplary. No changes needed.
- 4: Good. Minor improvements possible.
- 3: Acceptable. Noticeable weaknesses but not blocking.
- 2: Weak. Significant issues that reduce usefulness.
- 1: Unacceptable. Fails the dimension.

## 4. Advisory pass bar

A JudgeScore passes when BOTH conditions hold:
1. Every individual dimension score is at least 3 (no dimension is weak or worse).
2. The mean score across all four dimensions is at least 4.0 (overall quality is good).

This bar is advisory at Stage 4. It does not gate the CI build until a calibration
meta-eval (see calibration.py) confirms the judge is consistent and well-calibrated.
The bar values (MIN_PER_DIMENSION = 3, MIN_MEAN = 4.0) are defined in judge.py and can
be tuned once calibration data is available.

## 5. Grader design (injection pattern)

The actual LLM call is injected via the `grade` parameter of `make_judge()`. This mirrors
the pattern in report/llm_writer.py:

- Default path (CI, tests): pass a fake grader. No API key required. Deterministic.
- Live path: omit the `grade` argument. `make_judge()` uses `_anthropic_grader()`, which
  calls the Anthropic Messages API with tool-use structured output, forcing the model to
  return scores via the `emit_scores` tool.

The live test (`test_live_judge_scores_a_clean_report_highly`) is gated with
`@pytest.mark.skipif` and only runs when a real `ANTHROPIC_API_KEY` (starting `sk-ant-`,
length at least 50) is present. CI always skips it.

Model: `claude-sonnet-4-6`. The same model family used by the report writer, but with its
own system prompt and a different role (editor grading prose, not author producing it).

## 6. What the judge does NOT check

The judge must not re-score what the deterministic eval already owns:
- Citation coverage or validity.
- Factual grounding (numbers matching source artifacts).
- Section presence for the audience profile.
- Word count against the audience cap.

If a report passes the deterministic eval but scores poorly here, the failure is prose
quality, not correctness. The two evals are complementary, not overlapping.

## 7. Test cases (deterministic, fake grader)

All five tests in `tests/test_judge.py` run offline with a fake grader:

1. All dimensions at 5: scores, reasons, mean, and passes all correct.
2. One dimension at 2 (below MIN_PER_DIMENSION): passes = False even if mean is high.
3. All dimensions at 3 (mean = 3.0, below MIN_MEAN): passes = False.
4. Partial grader response (only one dimension returned): missing dimensions default to 0, passes = False.
5. `_anthropic_grader()` constructs without calling the API (callable check only).

The live test (case 6) calls the real API and asserts mean >= 3.0 on a clean two-section
exec report. This is a low bar by design: it checks the API call works, not that the
judge is well-calibrated.

## 8. What comes next (calibration)

The judge being advisory is deliberate. Before it can gate anything, a calibration
meta-eval (`calibration.py`) must confirm:
- The judge agrees with human raters on a labelled set of reports.
- It is consistent across repeated calls on the same report.
- The pass bar in section 4 separates good from bad reports reliably.

Until calibration passes, `JudgeScore.passes` is informational only.

## 9. What this unblocks

- The readability dimension of Stage 4 observability work.
- Calibration meta-eval (the next step before the judge gates anything).
- LLM-as-judge pattern available for other quality dimensions (tone, conciseness) if needed.
