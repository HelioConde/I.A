#!/usr/bin/env python3
"""One-step Windows Brain-SSD setup: install trusted model/runtime and start chat.

Only allowlisted GGUFs and the already-pinned llama.cpp CPU distribution can be
downloaded. Each download is SHA-256 verified before being published. No model
is executed until the separately validated native-runtime probe passes.
Private chat history, memories and the SSD research corpus are never changed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from install_windows_chat import (MODEL_BYTES, MODEL_RELATIVE, MODEL_SHA256,
                                  MODEL_URL, RUNTIME_RELATIVE, download_verified,
                                  install_runtime, verified_file)

MiB = 1024 * 1024


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    filename: str
    url: str
    sha256: str
    max_bytes: int
    min_bytes: int
    estimated_bytes: int
    recommended_ram_gb: int


MODELS = {
    "0.6b": ModelSpec(
        "0.6b", "Qwen3 0.6B Q8_0 (economico)", MODEL_RELATIVE.name, MODEL_URL,
        MODEL_SHA256, MODEL_BYTES, MODEL_BYTES, MODEL_BYTES, 4,
    ),
    "1.7b": ModelSpec(
        "1.7b", "Qwen3 1.7B Q4_K_M (intermediario)",
        "Qwen3-1.7B-Q4_K_M.gguf",
        "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/"
        "daeb8e2d528a760970442092f6bf1e55c3b659eb/Qwen3-1.7B-Q4_K_M.gguf",
        "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5",
        1_700_000_000, 900_000_000, 1_280_000_000, 8,
    ),
    "4b": ModelSpec(
        "4b", "Qwen3 4B Q4_K_M (melhor qualidade)",
        "Qwen3-4B-Q4_K_M.gguf",
        "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/"
        "Qwen3-4B-Q4_K_M.gguf",
        "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
        3_100_000_000, 2_000_000_000, 2_500_000_000, 8,
    ),
}


def model_destination(root: Path, selection: ModelSpec) -> Path:
    return Path(root) / "models" / selection.filename


def validate_existing_model(target: Path, spec: ModelSpec) -> bool:
    """Distinguish an absent download from a corrupt existing user file."""
    if not target.exists():
        return False
    if not target.is_file():
        raise FileExistsError("O destino do modelo existe e nao e um arquivo.")
    if target.stat().st_size < spec.min_bytes:
        raise FileExistsError(
            "O modelo existe, mas esta incompleto. Renomeie o GGUF manualmente "
            "antes de repetir; nenhum dado sera apagado automaticamente."
        )
    if not verified_file(target, sha256=spec.sha256,
                         exact_size=MODEL_BYTES if spec.key == "0.6b" else None):
        raise FileExistsError(
            "SHA-256 diferente do modelo oficial. O arquivo foi preservado; "
            "renomeie-o manualmente antes de tentar outro download."
        )
    with target.open("rb") as fh:
        if fh.read(4) != b"GGUF":
            raise ValueError("O modelo possui cabecalho GGUF invalido.")
    return True


def ensure_model(root: Path, spec: ModelSpec) -> tuple[Path, bool]:
    target = model_destination(root, spec)
    if validate_existing_model(target, spec):
        print("Modelo ja instalado e verificado:", target.name, flush=True)
        return target, False

    target.parent.mkdir(parents=True, exist_ok=True)
    available = shutil.disk_usage(target.parent).free
    required = spec.estimated_bytes + 256 * MiB
    if available < required:
        raise OSError(
            f"Espaco livre insuficiente. Necessario aproximadamente "
            f"{required // MiB} MiB no disco do modelo."
        )
    print(f"Baixando {spec.label} de um repositorio permitido...", flush=True)
    print(f"Arquivo: {target.name} | SHA-256 oficial: {spec.sha256}", flush=True)
    # Existing canonical installer streams to temporary .brainssd-staging-*
    # then atomically installs only if hash matches; never overwrites.
    download_verified(spec.url, target, sha256=spec.sha256,
                      max_size=spec.max_bytes,
                      exact_size=MODEL_BYTES if spec.key == "0.6b" else None)
    if not validate_existing_model(target, spec):
        raise RuntimeError("Falha ao validar o GGUF instalado.")
    return target, True


def prepare(root: Path, spec: ModelSpec) -> Path:
    """Install only missing dependencies, with no user-data mutations."""
    root = Path(root).resolve()
    if os.name != "nt" or sys.maxsize < 2**32:
        raise RuntimeError("Instalacao automatica exige Windows x64.")
    print(f"Selecionado: {spec.label}. Sem alterar o nucleo de pesquisa.", flush=True)
    destination = root / RUNTIME_RELATIVE
    if not (destination / "llama-completion.exe").is_file():
        print("llama.cpp oficial nao encontrado. Preparando runtime CPU...", flush=True)
    print(install_runtime(root), flush=True)
    path, downloaded = ensure_model(root, spec)
    if downloaded:
        print("Modelo baixado e SHA-256 conferido.", flush=True)
    return path


def start_chat(root: Path, spec: ModelSpec, *, web: bool, profile: str) -> int:
    args = [
        sys.executable, str(root / "tools" / "run_chat.py"),
        "--profile", profile, "--model-file", spec.filename,
        "--episodic-memory", "--cognitive-shadow", "--core-mode", "auto",
    ]
    if web:
        args.extend(["--web-search", "--web-provider", "auto"])
    print("Iniciando conversa local. Pressione Ctrl+C para encerrar.", flush=True)
    try:
        return subprocess.call(args, cwd=root)
    except KeyboardInterrupt:
        return 130


def main() -> int:
    parser = argparse.ArgumentParser(description="Preparar e iniciar Brain-SSD automaticamente")
    parser.add_argument("--model", choices=tuple(MODELS), required=True)
    parser.add_argument("--web", action="store_true",
                        help="Habilita o provedor auto (Wikipedia e noticias do Brasil), com autorizacao por pergunta")
    parser.add_argument("--profile", choices=("economia", "equilibrado"),
                        default="economia")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Baixa e verifica requisitos; nao abre o chat")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()
    spec = MODELS[args.model]
    print("Brain-SSD - instalacao automatica com modelos SHA-256 fixos")
    print("Downloads: Hugging Face e github.com/ggml-org (somente se necessario).")
    print("Historico e memorias privadas nao serao excluidos.")
    try:
        prepare(root, spec)
        # Probe the native official executable but do not load the model yet.
        doctor = [
            sys.executable, str(root / "tools" / "doctor_chat.py"),
            "--profile", args.profile, "--model-file", spec.filename, "--probe",
        ]
        print("Verificando integridade e executavel CPU...", flush=True)
        if subprocess.call(doctor, cwd=root) != 0:
            print("Diagnostico nao aprovado. Nao foi iniciado o chat.", file=sys.stderr)
            return 1
        if args.prepare_only:
            print("Preparacao concluida. Execute novamente sem --prepare-only.")
            return 0
        return start_chat(root, spec, web=args.web, profile=args.profile)
    except (ValueError, RuntimeError, FileExistsError, OSError) as exc:
        print(f"Preparacao interrompida: {exc}", file=sys.stderr)
        print("Arquivos locais e memorias foram preservados.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
