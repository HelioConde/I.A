from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.local_runtime.phase4ew import (
    DEVELOPMENT_STATUS,
    ENVIRONMENT,
    PHASE4E_INVALID_REASON,
    TARGET_8GB_STATUS,
    VALIDATION_TRACK,
    Phase4EWRunner,
    _exclusive_json,
    _outlier_flags,
    _stats,
)
from brain_ssd.local_runtime.windows_metrics import _perf_ms, _runtime_report


def test_phase4ew_classification_is_separate_from_canonical_phase4e() -> None:
    assert VALIDATION_TRACK == "PHASE_4E_W"
    assert ENVIRONMENT == "WINDOWS_NATIVE_FUNCTIONAL"
    assert DEVELOPMENT_STATUS == "EXPERIMENTAL_FUNCTIONAL_RUNTIME"
    assert PHASE4E_INVALID_REASON == "Phase 4E canonical physical baseline requires Debian/Linux native environment."
    assert TARGET_8GB_STATUS == "NOT_TESTED"


def test_statistics_preserve_outliers_and_report_variance() -> None:
    values = [10.0, 10.0, 11.0, 12.0, 100.0]
    result = _stats(values)
    flags = _outlier_flags(values)
    assert result["count"] == 5
    assert result["max"] == 100.0
    assert result["coefficient_of_variation"] > 0
    assert flags[-1] is True


def test_memory_growth_rules_do_not_replace_missing_metrics_with_zero() -> None:
    runner = object.__new__(Phase4EWRunner)
    trace = [
        {"working_set_bytes": 100, "private_bytes": 200, "available_system_ram_bytes": None, "process_cpu_time_seconds": 1, "handles": 3, "threads": None},
        {"working_set_bytes": 120, "private_bytes": 205, "available_system_ram_bytes": None, "process_cpu_time_seconds": 2, "handles": 3, "threads": None},
    ]
    result = runner._memory_analysis(trace)
    assert result["working_set_growth_bytes"] == 20
    assert result["private_bytes_growth_bytes"] == 5
    assert result["available_system_ram_bytes"]["count"] == 0
    assert result["threads"]["min"] is None


def test_immutable_result_writer_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    _exclusive_json(path, {"status": "PASS"})
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "PASS"
    with pytest.raises(FileExistsError):
        _exclusive_json(path, {"status": "FAIL"})


def test_current_runtime_load_and_build_capabilities_are_proven_from_stderr() -> None:
    stderr = (
        "0.01 I llama_completion: llama threadpool init, n_threads = 4\n"
        "0.02 I system_info: n_threads = 4 / 12 | CPU : AVX = 1 | AVX2 = 1 | F16C = 1 | FMA = 1 | OPENMP = 1 |\n"
        "0.03 I common_perf_print: load time = 1088.14 ms\n"
        "0.04 I common_perf_print: prompt eval time = 100.00 ms / 10 tokens (100.0 tokens per second)\n"
    )
    report = _runtime_report(stderr)
    assert _perf_ms(stderr, "load time") == 1088.14
    assert _perf_ms(stderr, "prompt eval time") == 100.0
    assert report["configured_threads"] == 4
    assert report["features"]["avx2"] is True
    assert report["features"]["blas"] is None
