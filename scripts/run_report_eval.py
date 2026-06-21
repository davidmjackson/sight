"""Run the report-quality eval (SS-1.5) and print the scoreboard.

    .venv/bin/python scripts/run_report_eval.py                      # default: compose (CI path)
    .venv/bin/python scripts/run_report_eval.py --llm                # live: real Anthropic writer
    .venv/bin/python scripts/run_report_eval.py --llm --judge-gate   # live: gate on readability

Pre-composer this reports RED by design. Once `compose` is wired it goes GREEN. Exits
non-zero unless fully green, so it doubles as the CI eval gate.

--llm requires a real ANTHROPIC_API_KEY (starts with sk-ant-, >=50 chars). If the key
is absent or invalid the script exits 2 immediately so CI never calls the API.

--judge-gate requires the same key. Runs the LLM-as-judge calibration meta-eval first;
only a trusted judge can block. Scores each eval report 5 times (median). Fails the run
if any scored report is below the readability bar. Any infra exception is treated as
non-blocking so a flaky API call cannot turn CI red.
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


def _score_one(judge, report, audience, n):
    """Score one report `n` times; return (median JudgeScore | None, surviving runs).

    Shared by the advisory pass (n=3) and the gate (n=5). Failed samples are dropped; if every
    sample fails the median is None. Reuses sample_judge's median logic by feeding it the already
    collected runs (the `_q=list(runs)` snapshot leaves `runs` intact for span printing).
    """
    from sprintsight.evals.judge import sample_judge

    runs = []
    for _ in range(n):
        try:
            runs.append(judge(report, audience))
        except Exception:  # noqa: BLE001 - advisory/gate path: drop a bad sample, keep going
            continue
    if not runs:
        return None, []
    median = sample_judge(lambda r, a, _q=list(runs): _q.pop(0), report, audience, n=len(runs))
    return median, runs


def _run_judge_pass(writer, n: int = 3) -> None:
    """Advisory LLM-judge readability pass, sampled. Key-gated; never changes the exit code."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key.startswith("sk-ant-") or len(key) < 50:
        print("\n[--judge] skipped: no real ANTHROPIC_API_KEY (advisory, CI-safe).")
        return
    from sprintsight.evals.judge import DIMENSIONS, make_judge
    from sprintsight.evals.report import build_cases

    judge = make_judge()
    print(f"\nReadability (advisory, LLM-judge, median of {n}):")
    for case in build_cases():
        report = writer(case.inputs)
        if report is None or report.insufficient_evidence:
            print(f"  {case.name:16} n/a (insufficient evidence)")
            continue
        audience = case.inputs.get("audience", "programme")
        median, runs = _score_one(judge, report, audience, n)
        if median is None:
            print(f"  {case.name:16} n/a (all judge samples failed)")
            continue
        flag = "PASS" if median.passes else "below-bar"
        cells = []
        for d in DIMENSIONS:
            lo = min(r.scores[d] for r in runs)
            hi = max(r.scores[d] for r in runs)
            span = f"{median.scores[d]}" if lo == hi else f"{median.scores[d]} ({lo}-{hi})"
            cells.append(f"{d}={span}")
        print(f"  {case.name:16} {flag}  mean={median.mean:.2f}  [{', '.join(cells)}]")


def _run_judge_gate(writer, n: int = 5, judge=None, run_calib=None) -> bool:
    """Blocking readability gate (live, key-holding runs only). Returns True iff it should block.

    Runs the calibration meta-eval first; only a trusted judge is allowed to block. Scores each
    eval report `n` times and takes the median. `judge`/`run_calib` are injectable for offline
    tests; they default to the real (key-gated) judge and calibration.
    """
    from sprintsight.evals.calibration import run_calibration
    from sprintsight.evals.judge import judge_gate_decision, make_judge
    from sprintsight.evals.report import build_cases

    judge = judge or make_judge()
    run_calib = run_calib or run_calibration
    # Calibration is single-sample by design: the anchors are deliberately extreme, so one run
    # separates them, and a wobble here fails safe (a calibration miss yields calibration_ok=False,
    # which never blocks). Only the report scoring needs the n-sample median.
    calibration_ok = run_calib(judge).pass_rate == 1.0

    medians: list[tuple[str, object]] = []
    print(f"\nReadability GATE (LLM-judge, median of {n}, calibration_ok={calibration_ok}):")
    for case in build_cases():
        report = writer(case.inputs)
        if report is None or report.insufficient_evidence:
            medians.append((case.name, None))
            print(f"  {case.name:16} n/a (insufficient evidence)")
            continue
        audience = case.inputs.get("audience", "programme")
        median, _runs = _score_one(judge, report, audience, n)
        medians.append((case.name, median))
        if median is None:
            print(f"  {case.name:16} n/a (all judge samples failed)")
        else:
            flag = "PASS" if median.passes else "below-bar"
            print(f"  {case.name:16} {flag}  mean={median.mean:.2f}")

    decision = judge_gate_decision(medians, calibration_ok)
    for line in decision.reasons:
        print(f"    {line}")
    print(f"\nJUDGE GATE: {'BLOCKS' if decision.blocks else 'OK'}")
    return decision.blocks


def main() -> int:
    writer = _select_writer()
    report = run_report_eval(writer)
    print(json.dumps(report.summary(), indent=2))
    print("\nPer-case:")
    for r in report.results:
        verdict = "PASS" if r.passed else "FAIL"
        checks = ", ".join(f"{a.name}={'ok' if a.passed else 'x'}" for a in r.assertions)
        print(f"  {r.name:16} {verdict}  [{checks}]")
        if r.error:
            print(f"                   error: {r.error}")
    if "--judge" in sys.argv:
        try:
            _run_judge_pass(writer)
        except Exception as exc:  # noqa: BLE001 - advisory pass must never change the exit code
            print(f"\n[--judge] error (advisory, ignored): {exc}")

    gate_blocks = False
    if "--judge-gate" in sys.argv:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key.startswith("sk-ant-") or len(key) < 50:
            print("ERROR: --judge-gate needs a real ANTHROPIC_API_KEY in the environment.")
            return 2
        try:
            gate_blocks = _run_judge_gate(writer)
        except Exception as exc:  # noqa: BLE001 - infra failure must not turn the build red
            print(f"\n[--judge-gate] error (infra; advisory, not blocking): {exc}")
            gate_blocks = False

    return 1 if (report.pass_rate != 1.0 or gate_blocks) else 0


if __name__ == "__main__":
    sys.exit(main())
