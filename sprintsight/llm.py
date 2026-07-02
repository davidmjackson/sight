"""Shared Anthropic tool-use call (structured output).

The LLM report writer (`report.llm_writer`) and the LLM-as-judge (`evals.judge`) make the
identical live call: define one tool, force `tool_choice` to it, then pull that tool_use
block's input back out. This is that call, written once, so the two cannot drift.

ZDR (zero data retention) is an account/org-level setting, not a per-request header, so
there are no extra_headers here; enable it in the Anthropic console if your org requires it.
The `anthropic` SDK is imported lazily so importing this module stays dependency-free.
"""

from typing import Any


def anthropic_tool_call(
    system: str,
    user: str,
    schema: dict[str, Any],
    *,
    tool_name: str,
    description: str,
    model: str,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Run one forced-tool-use completion and return the tool input dict ({} if none)."""
    import anthropic  # lazy: only needed on the live path

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    tool = {"name": tool_name, "description": description, "input_schema": schema}
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user}],
    )
    for block in msg.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    return {}
