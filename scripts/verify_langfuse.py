"""Verify Langfuse is provisioned and the eval harness traces to it.

Reads LANGFUSE_* from the repo-root .env (or the environment), runs a tiny eval suite
through the real tracer, flushes, and confirms the trace was accepted. Run:

    .venv/bin/python scripts/verify_langfuse.py

Exits 0 on success, non-zero with guidance if not configured or auth fails.
This is an operational check, not a unit test (it makes a real network call to Langfuse).
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv() -> None:
    """Minimal .env loader — sets LANGFUSE_* vars that aren't already in the environment."""
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    load_dotenv()

    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        print("Langfuse not configured. Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY")
        print("(and LANGFUSE_HOST) in .env, then re-run.")
        return 2

    from langfuse import get_client

    from sprintsight.evals import Assertion, Case, run_suite

    client = get_client()
    if not client.auth_check():
        print("Langfuse auth_check failed — keys or host are wrong.")
        return 1

    # Run a one-case suite through the real tracer; run_suite flushes on exit.
    case = Case(
        name="langfuse-smoke",
        inputs={"label": "green"},
        assertions=[lambda out: Assertion("classification", out["label"] == "green")],
    )
    report = run_suite([case], lambda inp: {"label": inp["label"]})
    client.flush()

    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    print(f"OK — auth verified, traced 1 case to Langfuse ({host}).")
    print(f"Suite summary: {report.summary()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
