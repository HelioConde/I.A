#!/usr/bin/env python3
"""Explicit, pinned Windows bootstrap for the local Brain-SSD *chat*.

No network access without --model, --runtime, or --all.
Checks SHA-256 BEFORE installing; never executes downloaded code during
installation. The upstream binary is separate from the frozen research Core.
It does not modify chat history, episodic notes, or the SSD corpus.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import urllib.request
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODEL_RELATIVE = Path("models/Qwen3-0.6B-Q8_0.gguf")
RUNTIME_RELATIVE = Path("third_party/llama.cpp/runtime-win-cpu-x64/bin")

# Official Qwen model — exact 639,446,688-byte revision; reject upstream drift.
MODEL_URL = ("https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/"
             "Qwen3-0.6B-Q8_0.gguf")
MODEL_BYTES = 639_446_688
MODEL_SHA256 = "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031"

# Official ggml-org Windows x64 CPU-only binary release, pinned for reproducibility.
# It is NOT the repository's historically frozen llama.cpp commit.
RUNTIME_TAG = "b11552"
RUNTIME_URL = ("https://github.com/ggml-org/llama.cpp/releases/download/"
               "b11552/llama-b11552-bin-win-cpu-x64.zip")
RUNTIME_SHA256 = "c00741179811ff903b515eae28bdeef1f47af6e81c49920c4e68b62954e056d6"
RUNTIME_MAX_COMPRESSED = 80 * 1024 * 1024
RUNTIME_MAX_UNPACKED = 300 * 1024 * 1024


def verified_file(path: Path, *, sha256: str, exact_size: int | None = None) -> bool:
    try:
        if not path.is_file() or (exact_size is not None and path.stat().st_size != exact_size):
            return False
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == sha256
    except OSError:
        return False


def download_verified(url: str, destination: Path, *, sha256: str,
                      max_size: int, exact_size: int | None = None) -> Path:
    """Download to a temporary sibling; atomically publish only matching bytes."""
    if max_size < 1 or (exact_size is not None and exact_size > max_size):
        raise ValueError("Limite de download inválido.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError("Destino já existe; nada foi sobrescrito.")
    staged = destination.parent / (".brainssd-staging-" + uuid.uuid4().hex)
    total = 0
    digest = hashlib.sha256()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "BrainSSD-Installer/1"})
        with urllib.request.urlopen(request, timeout=60) as source, staged.open("xb") as output:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > max_size:
                    raise ValueError("Download ultrapassou o limite esperado.")
                digest.update(chunk)
                output.write(chunk)
        if (exact_size is not None and total != exact_size) or digest.hexdigest() != sha256:
            raise ValueError("SHA-256 ou tamanho divergente; arquivo não instalado.")
        os.replace(staged, destination)
        return destination
    finally:
        if staged.exists():
            staged.unlink()


def install_model(root: Path = ROOT) -> str:
    target = root / MODEL_RELATIVE
    if verified_file(target, sha256=MODEL_SHA256, exact_size=MODEL_BYTES):
        return "Modelo oficial já está íntegro; nenhum download necessário."
    if target.exists():
        raise FileExistsError(
            "Há um GGUF no caminho esperado, mas ele não corresponde ao SHA-256 oficial. "
            "Renomeie o arquivo manualmente antes de instalar; não foi apagado."
        )
    download_verified(MODEL_URL, target, sha256=MODEL_SHA256,
                      exact_size=MODEL_BYTES, max_size=MODEL_BYTES)
    with target.open("rb") as verified_model:
        if verified_model.read(4) != b"GGUF":
            raise ValueError("Assinatura GGUF inválida após instalação.")
    return "GGUF oficial instalado, íntegro e pronto para o diagnóstico."


def safe_archive_entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Flatten only .exe/.dll, reject traversal and decompression bombs."""
    members: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in archive.infolist():
        original = info.filename.replace("\\", "/")
        parts = PurePosixPath(original).parts
        if info.is_dir():
            continue
        if original.startswith("/") or any(x in ("..", "") for x in parts) or ":" in original:
            raise ValueError("ZIP contém caminho inseguro; instalação recusada.")
        filename = parts[-1]
        if not filename.lower().endswith((".exe", ".dll")):
            continue
        if len(filename) > 160 or info.file_size > 90 * 1024 * 1024:
            raise ValueError("Artefato do runtime acima do limite.")
        total += info.file_size
        if total > RUNTIME_MAX_UNPACKED or len(members) > 128:
            raise ValueError("ZIP acima do limite de extração.")
        name = filename.lower()
        if name in members:
            raise ValueError("Artefatos repetidos no ZIP; instalação recusada.")
        members[name] = info
    if "llama-completion.exe" not in members:
        raise ValueError("ZIP não contém llama-completion.exe compatível.")
    return members


def install_runtime_archive(archive_path: Path, root: Path = ROOT) -> str:
    destination = root / RUNTIME_RELATIVE
    if destination.exists():
        raise FileExistsError(
            "Já existe um runtime comunitário nesta pasta. "
            "Renomeie a pasta manualmente para instalar outra versão."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".brainssd-runtime-", dir=destination.parent))
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            entries = safe_archive_entries(bundle)
            for name, member in entries.items():
                with bundle.open(member) as source, (staging / name).open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return f"Runtime CPU x64 instalado separadamente, versão {RUNTIME_TAG}; exige probe."


def install_runtime(root: Path = ROOT) -> str:
    destination = root / RUNTIME_RELATIVE
    if (destination / "llama-completion.exe").is_file():
        return ("Runtime de distribuição já está presente. Execute o diagnóstico "
                "para verificar se DLLs e modo CPU funcionam.")
    if destination.exists():
        raise FileExistsError("Pasta de runtime incompleta; não será sobrescrita automaticamente.")
    with tempfile.TemporaryDirectory(prefix="brainssd-download-") as temp:
        archive = Path(temp) / "runtime.zip"
        download_verified(RUNTIME_URL, archive, sha256=RUNTIME_SHA256,
                          max_size=RUNTIME_MAX_COMPRESSED)
        return install_runtime_archive(archive, root)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preparação verificável do chat Brain-SSD (Windows x64, CPU-only)"
    )
    parser.add_argument("--model", action="store_true", help="Baixar GGUF oficial (~639 MB)")
    parser.add_argument("--runtime", action="store_true",
                        help="Instalar binários CPU x64 oficiais do llama.cpp")
    parser.add_argument("--all", action="store_true", help="Executar as duas instalações")
    args = parser.parse_args()
    print("Brain-SSD — instalação explícita, oficial e verificada por SHA-256.")
    print("Modelo: Qwen/Qwen3-0.6B-GGUF (Q8_0)")
    print(f"Binário CPU: ggml-org/llama.cpp {RUNTIME_TAG} (não é o Core congelado)")
    print("Histórico, memórias e corpus SSD não são tocados.")
    if not (args.model or args.runtime or args.all):
        print("Somente auditoria. Use --all para solicitar os downloads.")
        print("Destino do modelo:", ROOT / MODEL_RELATIVE)
        print("Destino do runtime:", ROOT / RUNTIME_RELATIVE)
        return 0
    if os.name != "nt" or sys.maxsize < 2**32:
        print("Instalador limitado ao Windows x64. Nenhum download iniciado.")
        return 2
    try:
        if args.model or args.all:
            print(install_model())
        if args.runtime or args.all:
            print(install_runtime())
        print("Concluído. Execute DIAGNOSTICAR-CHAT-WINDOWS.bat antes do chat.")
        return 0
    except (ValueError, FileExistsError, OSError, zipfile.BadZipFile) as error:
        print(f"Instalação não concluída: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
