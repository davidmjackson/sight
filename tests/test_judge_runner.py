import importlib
import sys


def test_judge_pass_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mod = importlib.import_module("scripts.run_report_eval")
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

    mod = importlib.import_module("scripts.run_report_eval")

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
