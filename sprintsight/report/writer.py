"""The report-writer seam.

`ReportWriter` is any callable `inputs -> Report`. `null_writer` abstains (eval-first RED
signal). The deterministic `compose` lands in Story B; an Anthropic-backed writer is a later
drop-in behind the same callable (open-wiring item, not built here).
"""

from collections.abc import Callable
from typing import Any

from sprintsight.report.contract import Report

ReportWriter = Callable[[dict[str, Any]], Report]


def null_writer(inputs: dict[str, Any]) -> Report:
    """Abstains: empty report, so every case fails its assertions (RED by design)."""
    return Report(team=inputs["team"], audience=inputs["audience"])
