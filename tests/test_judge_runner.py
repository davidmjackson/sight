import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_report_eval.py"


def _load_runner():
    """Load scripts/run_report_eval.py by file path.

    `scripts/` is not an installed package, so `import scripts.run_report_eval` only
    resolves when the repo root happens to be on sys.path (e.g. `python -m pytest`).
    CI runs bare `pytest`, where it does not. Loading by path is robust to both.
    """
    spec = importlib.util.spec_from_file_location("run_report_eval", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_judge_pass_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mod = _load_runner()
    # The advisory pass must no-op (print a skip notice) and never raise when unkeyed.
    mod._run_judge_pass(lambda inputs: None)
    out = capsys.readouterr().out
    assert "judge" in out.lower() and "skip" in out.lower()


def test_score_one_returns_median_and_runs():
    from sprintsight.evals.judge import DIMENSIONS, make_judge
    from sprintsight.report.contract import Report

    mod = _load_runner()
    report = Report(team="Boreas", audience="exec", sections={"overall RAG": "Green."})
    # clarity walks [2,4,4] -> median 4; all other dims constant 4.
    state = {"i": 0}

    def grade(system, user, schema):
        i = state["i"]; state["i"] += 1
        clar = [2, 4, 4][i]
        return {d: {"score": (clar if d == "clarity" else 4), "reason": "x"} for d in DIMENSIONS}

    median, runs = mod._score_one(make_judge(grade=grade), report, "exec", n=3)
    assert median is not None
    assert median.scores["clarity"] == 4
    assert len(runs) == 3


def test_score_one_returns_none_when_all_samples_fail():
    from sprintsight.report.contract import Report

    mod = _load_runner()
    report = Report(team="Boreas", audience="exec", sections={"overall RAG": "Green."})

    def boom(report, audience):
        raise RuntimeError("api down")

    median, runs = mod._score_one(boom, report, "exec", n=3)
    assert median is None
    assert runs == []


def test_judge_pass_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mod = _load_runner()
    # The advisory pass must no-op (print a skip notice) and never raise when unkeyed.
    mod._run_judge_pass(lambda inputs: None)
    out = capsys.readouterr().out
    assert "judge" in out.lower() and "skip" in out.lower()


def test_judge_exception_does_not_change_exit_code(monkeypatch, capsys):
    """Advisory --judge pass raising must not alter the deterministic exit code.

    Invariant: even if _run_judge_pass raises, main() must return an int and the
    return value must match the deterministic eval result (0 when all cases pass).
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_report_eval.py", "--judge"])

    mod = _load_runner()

    # Patch _run_judge_pass to raise unconditionally (simulates network/API error).
    def _always_raise(writer):
        raise RuntimeError("simulated API failure")

    monkeypatch.setattr(mod, "_run_judge_pass", _always_raise)

    result = mod.main()

    # main() must return an int — not raise — and the deterministic eval is green (0).
    assert isinstance(result, int)
    assert result == 0

    # The error notice must appear in stdout so the operator can see what happened.
    out = capsys.readouterr().out
    assert "advisory" in out.lower() or "ignored" in out.lower()
