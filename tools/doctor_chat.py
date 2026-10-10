#!/usr/bin/env python3
"""Check prerequisites for the real Brain-SSD Windows chat without loading the model."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MIN_PLAUSIBLE_GGUF_BYTES = 64 * 1024 * 1024
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.runtime import PROFILES
from brain_ssd.local_runtime.backend import probe_llama, resolve_llama_executable
from brain_ssd.local_runtime.core_backend import resolve_server_executable
from brain_ssd.local_runtime.pipeline import INDEX_RELATIVE, MANIFEST_RELATIVE, MODEL_RELATIVE


def inspect_installation(root: Path, profile: str = "economia", probe: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    if profile not in PROFILES:
        raise ValueError(f"Perfil inválido: {profile}")
    expected_model = root / MODEL_RELATIVE
    model_exists = expected_model.is_file()
    model_size = 0
    model_magic = False
    model_readable = False
    if model_exists:
        try:
            model_size = expected_model.stat().st_size
            with expected_model.open("rb") as stream:
                model_magic = stream.read(4) == b"GGUF"
            model_readable = True
        except OSError:
            # Avoid a traceback containing Windows usernames or paths when
            # an antivirus or file permission blocks the model.
            pass
    mode = PROFILES[profile]["mode"]
    try:
        executable = resolve_server_executable(root) if mode == "persistent" else resolve_llama_executable(root)
        runtime_present = True
        runtime_error = None
    except FileNotFoundError as exc:
        executable, runtime_present, runtime_error = None, False, str(exc)
    runtime_probe: dict[str, Any] | None = None
    if probe and runtime_present and executable is not None:
        try:
            runtime_probe = probe_llama(executable) if mode == "subprocess" else {
                "note": "llama-server runtime presente; inicialização não executada pelo diagnóstico."
            }
        except (OSError, TimeoutError) as exc:
            runtime_probe = {"error": str(exc)}
    probe_passed = True
    if probe:
        if mode == "persistent":
            # The current doctor only checks llama-server file presence.
            # Do not pretend to have probed it as if it were llama-completion.
            probe_passed = True
        else:
            probe_passed = bool(runtime_probe is not None
                                and not runtime_probe.get("error")
                                and runtime_probe.get("version_return_code") == 0
                                and runtime_probe.get("devices_return_code") == 0)
    manifest = (root / MANIFEST_RELATIVE).is_file()
    index = (root / INDEX_RELATIVE).is_file()
    data_file = (root / MANIFEST_RELATIVE).with_name("brain.dat").is_file()
    required = {
        "python_3_11_or_newer": sys.version_info >= (3, 11),
        "model_gguf_valid_header": model_exists and model_magic,
        "model_plausible_size": model_size >= MIN_PLAUSIBLE_GGUF_BYTES,
        "cpu_runtime_found": runtime_present,
    }
    recommendations: list[str] = []
    if not required["python_3_11_or_newer"]:
        recommendations.append("Instale Python 3.11+ para Windows.")
    if model_exists and not model_readable:
        recommendations.append("O modelo existe, mas não pôde ser lido. Verifique permissões e antivírus.")
    if not model_exists:
        recommendations.append(f"Coloque o modelo Qwen3-0.6B-Q8_0.gguf em: {expected_model}")
    elif not model_magic:
        recommendations.append("O arquivo de modelo existe, mas não tem cabeçalho GGUF válido.")
    if not runtime_present:
        recommendations.append("Configure/compile o llama.cpp CPU-only (" + ("llama-server.exe" if mode == "persistent" else "llama-completion.exe") + ").")
    if not (manifest and index and data_file):
        recommendations.append("O corpus SSD está incompleto. O chat simples ainda poderá funcionar; a recuperação de conhecimento ficará desativada.")
    if model_exists and model_size < MIN_PLAUSIBLE_GGUF_BYTES:
        recommendations.append("O arquivo GGUF está pequeno demais para o Qwen3-0.6B Q8_0; confirme download completo.")
    if probe and not probe_passed:
        recommendations.append("O executável está presente mas falhou ao iniciar ou responder ao probe. Verifique DLLs do Visual C++/antivírus e a compilação do llama.cpp.")
    if runtime_probe and (runtime_probe.get("error") or runtime_probe.get("cpu_only_build") is False):
        recommendations.append("Verifique se o binário executa corretamente e está compilado em modo CPU-only.")
    return {
        "status": "READY_FOR_REAL_INFERENCE_TEST" if all(required.values()) and probe_passed else "MISSING_REQUIREMENTS",
        "ready_for_test": all(required.values()) and probe_passed,
        "probe_passed": probe_passed if probe and mode == "subprocess" else None,
        "profile": profile,
        "runtime_mode": mode,
        "platform": sys.platform,
        "root": str(root),
        "model": {"path": str(expected_model), "present": model_exists, "size_bytes": model_size, "gguf_header": model_magic},
        "runtime": {"path": str(executable) if executable else None, "found": runtime_present, "error": runtime_error, "probe": runtime_probe},
        "optional_ssd": {"manifest": manifest, "index": index, "brain_data": data_file, "available": manifest and index and data_file},
        "required": required,
        "recommendations": recommendations,
        "note": "Arquivos presentes não comprovam que o modelo gera respostas. Execute validate_chat_windows.py no Windows.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain-SSD Chat Windows — diagnóstico de instalação")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="economia")
    parser.add_argument("--probe", action="store_true", help="Executar --version/--list-devices do llama-completion")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = inspect_installation(ROOT, args.profile, args.probe)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("Brain-SSD — diagnóstico local")
        print("Perfil:", report["profile"])
        print("Status:", report["status"])
        for label, ok in report["required"].items():
            print((" OK  " if ok else " FALTA  ") + label)
        print("SSD:", "completo" if report["optional_ssd"]["available"] else "opcional, incompleto")
        for item in report["recommendations"]:
            print("-", item)
        if report["ready_for_test"]:
            print("Próximo passo: python tools/validate_chat_windows.py --profile " + args.profile)
    return 0 if report["ready_for_test"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
