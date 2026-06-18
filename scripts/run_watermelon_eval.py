"""Run the watermelon eval (SS-2.3) and print the scoreboard.

    .venv/bin/python scripts/run_watermelon_eval.py

With no detector wired (pre-SS-2.7) this reports RED by design. Once a detector is
passed to run_watermelon_eval(...), the same scoreboard shows the real result.
Exits non-zero if the suite is not fully green, so it can double as a CI/eval gate later.
"""

import json
import sys

from sprintsight.evals.watermelon import run_watermelon_eval
from sprintsight.graph.builder import graph_detector


def main() -> int:
    report = run_watermelon_eval(graph_detector())

    print(json.dumps(report.summary(), indent=2))
    print("\nPer-case:")
    for r in report.results:
        verdict = "PASS" if r.passed else "FAIL"
        checks = ", ".join(f"{a.name}={'ok' if a.passed else 'x'}" for a in r.assertions)
        print(f"  {r.name:8} {verdict}  [{checks}]")
        if r.error:
            print(f"           error: {r.error}")

    return 0 if report.pass_rate == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
