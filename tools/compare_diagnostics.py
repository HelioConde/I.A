#!/usr/bin/env python3
"""Compare two sanitized Brain-SSD diagnostic ZIPs, without requiring GGUF.

Only compares *observed metadata*. Refuses to infer model quality or real
memory savings from mock tests, differing profiles or incomplete samples.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import zipfile

MAX_SUMMARY_BYTES = 128 * 1024
METRICS = (
    ("chat_latency_ms", "p50", "ms", "lower"),
    ("inference_latency_ms", "p50", "ms", "lower"),
    ("time_to_first_token_ms", "p50", "ms", "lower"),
    ("native_peak_working_set_bytes", "maximum", "bytes", "lower"),
    ("python_working_set_bytes", "maximum", "bytes", "lower"),
)


def load_summary(path: Path) -> dict:
    """Read the only required ZIP member, with strict size and type bounds."""
    with zipfile.ZipFile(path, "r") as archive:
        info = archive.getinfo("summary.json")
        if info.file_size > MAX_SUMMARY_BYTES:
            raise ValueError("Resumo excede o limite do formato de diagnóstico.")
        payload = archive.read(info)
    record = json.loads(payload.decode("utf-8"))
    if not isinstance(record, dict) or record.get("schema_version") != 1 or record.get("category") != "SANITIZED_DIAGNOSTIC_ONLY":
        raise ValueError("Não é um pacote Brain-SSD de diagnóstico sanitizado.")
    return record


def _scalar(summary: dict, name: str, key: str) -> tuple[float, int] | None:
    record = summary.get(name)
    if not isinstance(record, dict):
        return None
    val, n = record.get(key), record.get("sample_count")
    if type(val) not in (int, float) or type(n) is not int or n <= 0:
        return None
    if not math.isfinite(val) or val < 0:
        return None
    return float(val), n


def _verified_real_run(summary: dict) -> bool:
    # CI runs may contain simulated "inference.done" events. Merely recording
    # memory/TTFT values is NOT evidence of Qwen on a physical computer.
    # A session qualifies only when an exported event was explicitly marked
    # as verified by a *real* Windows validation. Summary alone is insufficient.
    return False


def compare(base: dict, candidate: dict) -> dict:
    differences = {}
    for metric, key, unit, better in METRICS:
        original = _scalar(base, metric, key)
        current = _scalar(candidate, metric, key)
        if original is None or current is None:
            differences[metric] = {"status": "NOT_COMPARABLE", "reason": "Medição ausente"}
            continue
        before, n_before = original
        after, n_after = current
        differences[metric] = {
            "status": "OBSERVED_ONLY", "unit": unit, "baseline": before,
            "candidate": after, "baseline_samples": n_before,
            "candidate_samples": n_after,
            "absolute_delta": round(after - before, 3),
            "relative_delta_pct": round(100 * (after - before) / before, 2) if before > 0 else None,
            "direction_considered_better": better,
        }
    platforms_before = base.get("platforms") if isinstance(base.get("platforms"), dict) else {}
    platforms_after = candidate.get("platforms") if isinstance(candidate.get("platforms"), dict) else {}
    revisions_before = base.get("revisions") if isinstance(base.get("revisions"), list) else []
    revisions_after = candidate.get("revisions") if isinstance(candidate.get("revisions"), list) else []
    warnings = [
        "Diferenças de métricas não provam causalidade, qualidade cognitiva ou redução de RAM total.",
        "Este pacote não inclui texto das respostas; acerto factual não pode ser medido aqui.",
        "Sem medição real do modelo e hardware equiparado não existe ganho comprovado.",
    ]
    if platforms_before != platforms_after:
        warnings.append("Plataformas diferentes ou desconhecidas: comparação de recursos não é controlada.")
    if not base.get("chat_latency_ms") or not candidate.get("chat_latency_ms"):
        warnings.append("Uma das execuções não tem geração de chat concluída: nenhum ganho de chat pode ser inferido.")
    if not revisions_before or not revisions_after:
        warnings.append("Revisão de código não registrada em pelo menos uma execução.")
    return {
        "format": "BRAIN_SSD_DIAGNOSTIC_COMPARISON_V1",
        "evidence_level": "DESCRIPTIVE_METADATA_ONLY",
        "baseline": {
            "event_count": base.get("events_retained"),
            "platforms": platforms_before, "revisions": revisions_before,
        },
        "candidate": {
            "event_count": candidate.get("events_retained"),
            "platforms": platforms_after, "revisions": revisions_after,
        },
        "metrics": differences,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparar dois pacotes sanitizados do Brain-SSD")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    try:
        result = compare(load_summary(args.baseline), load_summary(args.candidate))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print("Pacote inválido ou indisponível: " + type(exc).__name__, file=sys.stderr)
        return 2
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
