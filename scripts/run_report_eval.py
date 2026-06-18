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
    return 0 if report.pass_rate == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
