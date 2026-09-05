from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.backend import LocalLlamaCppBackend, executable_candidates, resolve_llama_executable
from brain_ssd.local_runtime.capabilities import (
    PHASE4E_INVALID_REASON,
    UNSUPPORTED,
    WINDOWS_NATIVE_FUNCTIONAL,
    EnvironmentCapabilities,
)
from brain_ssd.local_runtime.pipeline import LocalBrainSSD, clean_answer
from brain_ssd.local_runtime.windows_metrics import _perf_ms, _perf_number, _perf_tokens, _runtime_report, run_measured_windows


def test_windows_capability_matrix_is_honest() -> None:
    detected = EnvironmentCapabilities.detect(ROOT, system_name="Windows", os_name="nt")
    assert detected.environment_type == WINDOWS_NATIVE_FUNCTIONAL
    assert detected.phase4e_valid is False
    assert detected.phase4e_invalid_reason == PHASE4E_INVALID_REASON
    assert detected.capabilities["memory_mapped_brain"].status == "SUPPORTED"
    assert detected.capabilities["physical_ssd_io"].status == "DEGRADED"
    for name in ("procfs_metrics", "cgroups_v2", "psi_pressure", "madvise_cold", "madvise_pageout", "mincore_residency"):
        assert detected.capabilities[name].status == UNSUPPORTED
        assert detected.capabilities[name].reason == "unsupported_on_windows"


def test_linux_compatibility_does_not_claim_phase4e() -> None:
    detected = EnvironmentCapabilities.detect(ROOT, system_name="Linux", os_name="posix")
    assert detected.environment_type == "LINUX_COMPATIBLE"
    assert detected.phase4e_valid is False
    assert detected.capabilities["windows_working_set"].status == UNSUPPORTED


def test_executable_resolution_supports_spaces_and_platform_suffix(tmp_path: Path) -> None:
    explicit = tmp_path / "runtime with spaces" / "llama-completion.exe"
    explicit.parent.mkdir()
    explicit.write_bytes(b"MZ")
    assert resolve_llama_executable(tmp_path, explicit, windows=True) == explicit.resolve()
    windows = executable_candidates(tmp_path, windows=True)
    linux = executable_candidates(tmp_path, windows=False)
    assert all(path.name.endswith(".exe") for path in windows)
    assert all(not path.name.endswith(".exe") for path in linux)


def test_local_backend_reuses_frozen_cpu_flags(tmp_path: Path) -> None:
    executable = tmp_path / "llama completion.exe"
    model = tmp_path / "model with spaces.gguf"
    executable.write_bytes(b"MZ")
    model.write_bytes(b"GGUF")
    command = list(LocalLlamaCppBackend(executable, model).command(GenerationRequest("olá", max_tokens=17)))
    assert command[0] == str(executable)
    assert command[command.index("--model") + 1] == str(model)
    assert command[command.index("--prompt") + 1] == "olá"
    assert command[command.index("--device") + 1] == "none"
    assert "--conversation" in command and "--single-turn" in command
    assert "--no-warmup" in command and command[command.index("--reasoning") + 1] == "off"


def test_local_output_cleanup_removes_only_transport_markers() -> None:
    assert clean_answer("NO_KNOWLEDGE. [end of text]\n") == "NO_KNOWLEDGE."
    assert clean_answer("<think>hidden</think>resposta > ") == "resposta"


def test_current_llama_perf_prefix_and_run_count_are_parsed() -> None:
    stderr = (
        "0.06 I common_perf_print: prompt eval time = 1087.70 ms / 15 tokens (13.79 tokens per second)\n"
        "0.07 I common_perf_print:        eval time = 3211.10 ms / 6 runs (1.87 tokens per second)\n"
    )
    assert _perf_number(stderr, "prompt eval time") == 13.79
    assert _perf_number(stderr, "eval time") == 1.87
    assert _perf_tokens(stderr, "prompt eval time") == 15
    assert _perf_tokens(stderr, "eval time") == 6


@pytest.mark.skipif(os.name != "nt", reason="Windows process counters are Windows-only")
def test_measured_subprocess_preserves_unicode_and_space_argument() -> None:
    expected = "caminho com espaços — ação"
    result = run_measured_windows([sys.executable, "-c", "import sys;print(sys.argv[1])", expected])
    assert result["return_code"] == 0
    assert result["stdout"].strip() == expected
    assert result["metrics"]["physical_read_bytes"] is None
    assert "cpu_percent_total_average" in result["metrics"]
    assert "cpu_percent_total_peak" in result["metrics"]
    assert "not a physical SSD" in result["measurement_semantics"]["read_transfer_bytes_delta"]


def test_real_windows_retrieval_uses_mmap_and_known_unknown_queries() -> None:
    with LocalBrainSSD(ROOT) as runtime:
        known = runtime.retrieve("Why can repeated json.dump calls create invalid JSON?")
        unknown = runtime.retrieve("What is the exact cache size of the Python OrionDB driver?")
    assert known["status"] == "OK"
    assert known["activated_pages"]
    assert known["storage"]["logical_page_bytes"] <= 4 * 1024**2
    assert known["storage"]["checksum_errors"] == 0
    assert unknown["status"] == "NO_KNOWLEDGE"
    assert unknown["activated_pages"] == []
    assert unknown["record_ids"] == []


def test_generated_windows_results_are_noncanonical_when_present() -> None:
    result_dir = ROOT / "results/windows_native"
    for path in result_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["environment_type"] == WINDOWS_NATIVE_FUNCTIONAL
        assert payload["phase4e_valid"] is False
        assert payload["phase4e_invalid_reason"] == PHASE4E_INVALID_REASON
