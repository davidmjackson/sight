"""Grade the readability judge against the calibration anchors (Stage 4, SS-7). Live, key-gated.

    .venv/bin/python scripts/run_calibration.py

Exits 0 only if the judge ranks every anchor as expected (good -> pass, bad -> below-bar),
1 if it does not, 2 if no real ANTHROPIC_API_KEY is set so CI never calls the API.
"""

import json
import os
import sys

from sprintsight.evals.calibration import run_calibration
from sprintsight.evals.judge import make_judge


def main() -> int:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key.startswith("sk-ant-") or len(key) < 50:
        print("ERROR: run_calibration needs a real ANTHROPIC_API_KEY in the environment.")
        return 2
    report = run_calibration(make_judge())
    print(json.dumps(report.summary(), indent=2))
    print("\nPer-anchor:")
    for r in report.results:
        verdict = "PASS" if r.passed else "FAIL"
        detail = r.assertions[0].detail if r.assertions else r.error
        print(f"  {r.name:16} {verdict}  {detail}")
    return 0 if report.pass_rate == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
