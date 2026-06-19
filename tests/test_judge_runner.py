import importlib


def test_judge_pass_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mod = importlib.import_module("scripts.run_report_eval")
    # The advisory pass must no-op (print a skip notice) and never raise when unkeyed.
    mod._run_judge_pass(lambda inputs: None)
    out = capsys.readouterr().out
    assert "judge" in out.lower() and "skip" in out.lower()
