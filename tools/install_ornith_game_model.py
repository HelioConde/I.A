#!/usr/bin/env python3
"""Opt-in verified Ornith-1.5-9B Q4_K_M GGUF for Luna GameDev.

Does not change Luna's default model, chat history or existing Qwen files.
Verify the provider-published LFS SHA-256; never trust a file just by name.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
MODEL_FILE="Ornith-1.5-9B-Q4_K_M.gguf"
MODEL_REVISION="9a5e9dc"
MODEL_REPOSITORY="ornith-ai/Ornith-1.5-9B-GGUF"
MODEL_URL="https://huggingface.co/"+MODEL_REPOSITORY+"/resolve/"+MODEL_REVISION+"/"+MODEL_FILE
MODEL_SHA256="70c112196e0b7023803c9762752e46d29e612a92c83f995bc3ba1ceb07e8fab6"
MODEL_MAX_BYTES=6_500_000_000  # exact SHA-256 is mandatory; bound rejects oversized downloads


def install(root:Path=ROOT)->str:
    from install_windows_chat import verified_file,download_verified
    target=root/"models"/MODEL_FILE
    if verified_file(target,sha256=MODEL_SHA256):
        return "Ornith-1.5-9B GGUF já instalado e verificado por SHA-256."
    if target.exists():
        raise FileExistsError("Modelo existente tem SHA-256 incorreto; não sobrescrever.")
    download_verified(MODEL_URL,target,sha256=MODEL_SHA256,max_size=MODEL_MAX_BYTES)
    with target.open("rb") as f:
        if f.read(4)!=b"GGUF":
            target.unlink()
            raise ValueError("Arquivo baixado não possui assinatura GGUF.")
    return "Modelo Ornith-1.5-9B validado e instalado. Teste antes de promovê-lo."


def main()->int:
    p=argparse.ArgumentParser(description="Luna GameDev: Ornith-1.5 9B SHA-256 verified installer")
    p.add_argument("--confirm-download",action="store_true",help="Autoriza download de ~5,78 GB")
    p.add_argument("--allow-linux-ci",action="store_true",
                   help="Somente GitHub Actions Linux: exige CI=true")
    args=p.parse_args()
    print("Modelo:",MODEL_REPOSITORY+"@"+MODEL_REVISION+"/"+MODEL_FILE)
    print("SHA-256:",MODEL_SHA256)
    print("Tamanho aproximado: 5,78 GB; armazenamento adicional necessário para KV cache.")
    if not args.confirm_download:
        print("Dry run: nenhum download iniciado. Use --confirm-download para autorizar.")
        return 0
    linux_ci=args.allow_linux_ci and os.name!="nt" and os.environ.get("CI","").lower()=="true"
    windows=os.name=="nt" and sys.maxsize>=2**32
    if not (windows or linux_ci):
        print("Suporte a Windows x64 ou GitHub Actions Linux CI autorizado somente.",file=sys.stderr)
        return 2
    try:
        print(install())
        return 0
    except (OSError,ValueError) as exc:
        print("Instalação falhou:",type(exc).__name__,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
