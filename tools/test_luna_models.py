#!/usr/bin/env python3
"""Opt-in A/B benchmark of official Qwen3 0.6B vs Qwen3 4B on Luna.

The default action is offline status. --download explicitly fetches a
pinned official GGUF and verifies SHA256. --compare performs real CPU
inference sequentially, never loading both models at once. No settings
or original model files are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.performance import windows_memory
from brain_ssd.chat.runtime import LocalChatRuntime
from brain_ssd.chat.server import ChatEngine

BASELINE = "Qwen3-0.6B-Q8_0.gguf"
CANDIDATE = "Qwen3-4B-Q8_0.gguf"
SOURCE = (
    "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/"
    "bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q8_0.gguf"
)
CANDIDATE_SHA256 = "8c2f07f26af9747e41988551106f149b03eb9b5cb6df636027b6bf6278473300"
MIN_4B = 4_000_000_000
MIN_FREE_DISK = 6 * 1024 ** 3
MIN_FREE_RAM = 6 * 1024 ** 3
TEST_CASES = (
    ("arithmetic", "Responda apenas com um número: quanto é 37 vezes 18?"),
    ("coding", "Em Python, qual é o resultado de len([3, 5, 8]) + 2? Explique em uma frase."),
    ("voice_ptbr", "Explique em português brasileiro, em duas frases curtas, o que é memória RAM para um iniciante."),
    ("truthfulness", "Qual a diferença entre dizer 'posso consultar uma fonte' e 'consultei uma fonte'? Responda em duas frases."),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local_model_status(models: Path) -> dict[str, Any]:
    status = {}
    for filename in (BASELINE, CANDIDATE):
        target = models / filename
        exists = target.is_file() and not target.is_symlink()
        size = target.stat().st_size if exists else 0
        header = False
        if exists:
            with target.open("rb") as stream:
                header = stream.read(4) == b"GGUF"
        status[filename] = {
            "present": exists, "bytes": size, "header_gguf": header,
            "plausible_size": size >= (MIN_4B if filename == CANDIDATE else 400_000_000),
        }
    return status


def download_candidate(models: Path, *, opener=urllib.request.urlopen) -> dict:
    models.mkdir(parents=True, exist_ok=True)
    destination = models / CANDIDATE
    part = models / (CANDIDATE + ".download-incomplete")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("O arquivo de destino já existe. Verifique-o; nunca sobrescreveremos o GGUF.")
    if part.exists() or part.is_symlink():
        raise FileExistsError("Download incompleto anterior existe; confira/remova manualmente o arquivo .download-incomplete.")
    if shutil.disk_usage(models).free < MIN_FREE_DISK:
        raise OSError("Espaço livre insuficiente. Recomenda-se ao menos 6 GiB livres no SSD.")
    print("Download solicitado pelo usuário: Qwen/Qwen3-4B-GGUF Q8_0 (4,28 GB).", flush=True)
    print("Somente o arquivo de pesos oficial; nenhum arquivo do 0.6B será modificado.", flush=True)
    digest = hashlib.sha256()
    received = 0
    next_update = 128 * 1024 * 1024
    try:
        # HTTPS redirect to the storage CDN is handled by urllib.
        with opener(SOURCE, timeout=120) as response, part.open("xb") as target:
            for chunk in iter(lambda: response.read(4 * 1024 * 1024), b""):
                received += len(chunk)
                if received > 5_000_000_000:
                    raise ValueError("O download excedeu o tamanho plausível do GGUF oficial.")
                target.write(chunk)
                digest.update(chunk)
                if received >= next_update:
                    print(f"Recebidos: {received / (1024**3):.2f} GiB", flush=True)
                    next_update += 128 * 1024 * 1024
        if received < MIN_4B or digest.hexdigest() != CANDIDATE_SHA256:
            raise ValueError("SHA256 ou tamanho do modelo não corresponde ao GGUF oficial. Descartando cópia.")
        with part.open("rb") as stream:
            if stream.read(4) != b"GGUF":
                raise ValueError("O modelo baixado não possui cabeçalho GGUF.")
        # Atomic publish. Never overwrite an existing working GGUF.
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("O destino surgiu durante o download. Não vamos sobrescrever.")
        part.rename(destination)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return {"downloaded": True, "file": CANDIDATE,
            "bytes": received, "sha256": digest.hexdigest()}


def check_comparison_prerequisites(models: Path, *, unsafe_low_ram: bool = False,
                                   memory_probe=windows_memory) -> dict:
    status = local_model_status(models)
    for filename, item in status.items():
        if not item["present"] or not item["header_gguf"] or not item["plausible_size"]:
            raise ValueError(f"Modelo ausente ou incompleto: {filename}. Confira models/ antes de comparar.")
    actual = sha256_file(models / CANDIDATE)
    if actual != CANDIDATE_SHA256:
        raise ValueError("O Qwen3-4B-Q8_0.gguf não corresponde ao SHA256 oficial; benchmark recusado.")
    available = memory_probe()
    if available is None:
        if not unsafe_low_ram:
            raise ValueError("RAM disponível não pôde ser medida. Use --allow-low-ram explicitamente somente se aceitar o risco.")
    elif available.available < MIN_FREE_RAM and not unsafe_low_ram:
        raise ValueError(f"RAM disponível: {available.available / 2**30:.2f} GiB. "
                         "É recomendado ter pelo menos 6 GiB livres; feche outros programas "
                         "ou use --allow-low-ram conscientemente.")
    return {
        "model_sha256": {BASELINE: sha256_file(models / BASELINE), CANDIDATE: actual},
        "free_ram_before_bytes": available.available if available else None,
        "total_ram_bytes": available.total if available else None,
        "ram_safety_override": bool(unsafe_low_ram),
    }


def execute_case(engine: ChatEngine, prompt: str, *, tokens: int = 96) -> dict:
    start = time.perf_counter()
    reply = engine.ask(prompt, [], response_tokens=tokens, web_search=False)
    elapsed = time.perf_counter() - start
    if reply.get("mode") == "local_command" or not engine.status().get("inference_verified"):
        raise RuntimeError("O pedido foi respondido por regra local; inferência Qwen não comprovada.")
    return {
        "elapsed_s": round(elapsed, 4), "answer": str(reply.get("answer", "")),
        "completion": reply.get("completion"),
        "generated_tokens": reply.get("generated_tokens"),
        "metrics": reply.get("metrics", {}),
        "answer_complete": reply.get("answer_complete"),
        "generation_limit": reply.get("generation_limit"),
    }


def run_comparison(models: Path, *, profile: str, output: Path, unsafe_low_ram: bool = False) -> dict:
    if os.name != "nt":
        raise OSError("Benchmark de inferência é destinado ao Windows com runtime llama.cpp local.")
    provenance = check_comparison_prerequisites(models, unsafe_low_ram=unsafe_low_ram)
    report: dict[str, Any] = {
        "schema": 1, "kind": "luna_qwen_0_6b_vs_4b",
        "status": "in_progress", "utc": datetime.now(timezone.utc).isoformat(),
        "conditions": {
            "quantization": "Q8_0 for both", "core_mode": "subprocess",
            "profile": profile, "context": "per-profile", "response_tokens": 96,
            "sampling": "Luna original, temperature=0.7 (non-deterministic)",
            "order": [BASELINE, CANDIDATE], "os_file_cache": "not controlled",
            "no_web_requests_for_prompts": True, "models_loaded_sequentially": True,
            "quality_evaluation": "manual; more parameters do not guarantee better answers",
        },
        "provenance": provenance, "models": {},
        "notice": ("Resultados desta máquina são medidos; não são métricas do runtime Brain-SSD "
                   "com streaming de pesos. Respostas são armazenadas apenas no JSON local."),
    }
    output.parent.mkdir(parents=True, exist_ok=True)

    def persist() -> None:
        tmp = output.with_name(output.name + ".tmp")
        tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(output)

    persist()
    for filename in (BASELINE, CANDIDATE):
        print(f"\nModelo de teste: {filename}. Um modelo de cada vez.", flush=True)
        entry: dict = {"status": "running", "cases": []}
        report["models"][filename] = entry
        persist()
        engine = ChatEngine(lambda model=filename: LocalChatRuntime(
            ROOT, profile=profile, core_mode="subprocess", model_file=model))
        try:
            engine.start()
            if engine.status().get("status") != "ready":
                raise RuntimeError("Modelo não ficou pronto após start().")
            entry["runtime_status"] = engine.status()
            for case_id, prompt in TEST_CASES:
                print(f"  Teste: {case_id}", flush=True)
                entry["cases"].append({"id": case_id, "question": prompt,
                                       **execute_case(engine, prompt)})
                persist()
            entry["status"] = "measured"
        except Exception as exc:
            entry["status"] = "failed"
            entry["error"] = type(exc).__name__ + ": " + str(exc)[:250]
            persist()
            raise
        finally:
            engine.close()
    report["status"] = "measured"
    persist()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--download", action="store_true",
                           help="Baixar 4,28 GB oficiais e validar SHA256, somente com consentimento explícito")
    operation.add_argument("--compare", action="store_true",
                           help="Executar ambos os modelos Q8_0 sequencialmente, offline")
    parser.add_argument("--profile", choices=("economia", "equilibrado", "rapido"),
                        default="equilibrado")
    parser.add_argument("--allow-low-ram", action="store_true",
                        help="Assumir explicitamente o risco se houver menos de 6 GiB RAM livres")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "results" / "model_comparison" / "qwen3-ab.json")
    args = parser.parse_args(argv)
    models = ROOT / "models"
    try:
        if args.download:
            result = download_candidate(models)
        elif args.compare:
            result = run_comparison(models, profile=args.profile,
                                    output=args.output, unsafe_low_ram=args.allow_low_ram)
            result = {"status": result["status"], "report": str(args.output)}
        else:
            # Default status is offline: it never downloads a model or runs Qwen.
            result = {
                "status": "offline_check", "models": local_model_status(models),
                "candidate": "Official Qwen/Qwen3-4B-GGUF Q8_0, SHA256 pinned",
                "download_requested": False, "inference_requested": False,
            }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        print("Comparação Luna interrompida: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
