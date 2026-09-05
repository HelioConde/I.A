from __future__ import annotations

import os
from typing import Any, Callable, Sequence

from brain_ssd.local_runtime.windows_metrics import run_measured_windows


def run_measured(command: Sequence[str], on_first_output: Callable[[], None] | None = None) -> dict[str, Any]:
    if os.name == "nt":
        return run_measured_windows(command, on_first_output=on_first_output)
    from brain_ssd.telemetry import run_measured as portable_run_measured

    measured = portable_run_measured(command, sample_interval_s=0.025)
    if on_first_output and measured.get("stdout"):
        on_first_output()
    return measured
