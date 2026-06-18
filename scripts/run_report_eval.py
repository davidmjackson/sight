"""Run the report-quality eval (SS-1.5) and print the scoreboard.

    .venv/bin/python scripts/run_report_eval.py

Pre-composer this reports RED by design. Once `compose` is wired it goes GREEN. Exits
non-zero unless fully green, so it doubles as the CI eval gate.
"""

import json
import sys

from sprintsight.evals.report import run_report_eval
from sprintsight.report.writer import compose


def main() -> int:
    report = run_report_eval(compose)
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
