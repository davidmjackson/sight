"""Run the report-quality eval (SS-1.5) and print the scoreboard.

    .venv/bin/python scripts/run_report_eval.py           # default: compose (CI path)
    .venv/bin/python scripts/run_report_eval.py --llm     # live: real Anthropic writer

Pre-composer this reports RED by design. Once `compose` is wired it goes GREEN. Exits
non-zero unless fully green, so it doubles as the CI eval gate.

--llm requires a real ANTHROPIC_API_KEY (starts with sk-ant-, >=50 chars). If the key
is absent or invalid the script exits 2 immediately so CI never calls the API.
"""

import json
import os
import sys

from sprintsight.evals.report import run_report_eval
from sprintsight.graph.builder import graph_writer
from sprintsight.report.llm_writer import make_llm_writer
from sprintsight.report.writer import compose


def _select_writer() -> object:
    if "--llm" in sys.argv:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key.startswith("sk-ant-") or len(key) < 50:
            print("ERROR: --llm needs a real ANTHROPIC_API_KEY in the environment.")
            sys.exit(2)
        return graph_writer(make_llm_writer())
    return graph_writer(compose)


def _run_judge_pass(writer) -> None:
    """Advisory LLM-judge readability pass. Key-gated; never changes the exit code."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key.startswith("sk-ant-") or len(key) < 50:
        print("\n[--judge] skipped: no real ANTHROPIC_API_KEY (advisory, CI-safe).")
        return
    from sprintsight.evals.judge import make_judge
    from sprintsight.evals.report import build_cases

    judge = make_judge()
    print("\nReadability (advisory, LLM-judge):")
    for case in build_cases():
        report = writer(case.inputs)
        if report is None or report.insufficient_evidence:
            print(f"  {case.name:16} n/a (insufficient evidence)")
            continue
        score = judge(report, case.inputs.get("audience", "programme"))
        flag = "PASS" if score.passes else "below-bar"
        dims = ", ".join(f"{d}={score.scores[d]}" for d in score.scores)
        print(f"  {case.name:16} {flag}  mean={score.mean:.1f}  [{dims}]")


def main() -> int:
    report = run_report_eval(_select_writer())
    print(json.dumps(report.summary(), indent=2))
    print("\nPer-case:")
    for r in report.results:
        verdict = "PASS" if r.passed else "FAIL"
        checks = ", ".join(f"{a.name}={'ok' if a.passed else 'x'}" for a in r.assertions)
        print(f"  {r.name:16} {verdict}  [{checks}]")
        if r.error:
            print(f"                   error: {r.error}")
    if "--judge" in sys.argv:
        _run_judge_pass(_select_writer())
    return 0 if report.pass_rate == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
