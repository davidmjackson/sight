"""Deterministic eval harness (SS-2.2).

Generic runner that both the watermelon eval (SS-1.4 / SS-2.3) and the report-quality
eval (SS-1.5, Stage 2) plug into. Deterministic-first; LLM-as-judge is deferred to Stage 4.
"""

from sprintsight.evals.harness import (
    Assertion,
    Case,
    CaseResult,
    SuiteReport,
    run_suite,
)

__all__ = ["Assertion", "Case", "CaseResult", "SuiteReport", "run_suite"]
