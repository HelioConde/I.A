from __future__ import annotations

from pathlib import Path

from brain_ssd.local_runtime.windows_core_experiment_1b import (
    CONDITION_A,
    CONDITION_B,
    CONDITION_C,
    CONDITIONS,
    EXPERIMENT,
    EXPERIMENT_NAME,
    SEED,
    _effect,
    _linear_regression,
    context_payload,
    deterministic_order,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/brain_ssd/local_runtime/windows_core_experiment_1b.py"


def test_runtime_abc_resolution_labels_are_distinct() -> None:
    assert CONDITIONS == (CONDITION_A, CONDITION_B, CONDITION_C)
    assert len(set(CONDITIONS)) == 3


def test_same_experimental_build_targets_exist() -> None:
    build = ROOT / "third_party/llama.cpp/build-win-persistent/bin"
    assert (build / "llama-completion.exe").is_file()
    assert (build / "llama-server.exe").is_file()


def test_frozen_hash_checks_are_explicit() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "baseline_hash_exact" in source
    assert "server_hash_preserved" in source
    assert "frozen_results_preserved" in source


def test_token_payload_generator_is_diverse_and_bounded() -> None:
    short = context_payload(128)
    long = context_payload(1024)
    assert len(long) > len(short)
    assert "AZUL" in short and "/no_think" in short
    assert len(set(long.split())) > 30


def test_actual_token_reporting_is_backend_derived() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert '"actual_prompt_tokens": metrics.get("prompt_tokens")' in source


def test_randomized_order_is_deterministic() -> None:
    items = list(range(30))
    assert deterministic_order(items, SEED) == deterministic_order(items, SEED)
    assert deterministic_order(items, SEED) != items


def test_metrics_schema_contains_required_windows_fields() -> None:
    core_source = (ROOT / "src/brain_ssd/local_runtime/core_backend.py").read_text(encoding="utf-8")
    for field in ("cpu_user_seconds", "cpu_kernel_seconds", "cpu_percent_total_peak", "read_transfer_bytes_delta", "working_set_bytes_max", "private_bytes_max"):
        assert field in core_source


def test_context_hash_equivalence_is_required() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert '"context_hash_equivalent"' in source
    assert '"generation_config_hash"' in source


def test_causal_effect_summary_sign_convention() -> None:
    assert _effect(100.0, 70.0) == {"delta": -30.0, "percent_vs_base": -30.0}
    fit = _linear_regression([(0.0, 10.0), (100.0, 30.0), (200.0, 50.0)])
    assert fit["slope_ms_per_token"] == 0.2
    assert fit["r_squared"] == 1.0


def test_theoretical_estimate_is_labeled_only() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert '"label": "THEORETICAL_ONLY"' in source
    assert "quality preservation" not in source.casefold() or "NOT_TESTED" in source


def test_no_phase4f_or_prefetch_mutation() -> None:
    assert EXPERIMENT == "WCRE_1B"
    assert EXPERIMENT_NAME == "WINDOWS_RUNTIME_CAUSALITY_CONTEXT_COST"
    source = SOURCE.read_text(encoding="utf-8")
    assert '"phase4f_started": False' in source
    assert '"phase5_started": False' in source
    assert '"prefetch_enabled": False' in source
