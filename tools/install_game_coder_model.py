#!/usr/bin/env python3
"""Opt-in, hash-verified official Qwen3-4B Q4_K_M GameDev model installation.

This is separate from the canonical Brain-SSD 0.6B model installer.
Downloads no executable code and never overwrites an existing GGUF.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
MODEL_FILENAME="Qwen3-4B-Q4_K_M.gguf"
MODEL_REVISION="bc640142c66e1fdd12af0bd68f40445458f3869b"
MODEL_URL=(
    "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/"
    +MODEL_REVISION+"/"+MODEL_FILENAME
)
MODEL_BYTES=2_497_280_256
MODEL_SHA256="7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"


def install(root:Path=ROOT)->str:
    from install_windows_chat import verified_file,download_verified
    target=root/"models"/MODEL_FILENAME
    if verified_file(target,sha256=MODEL_SHA256,exact_size=MODEL_BYTES):
        return "Qwen3-4B Q4_K_M já está íntegro. Nenhum download feito."
    if target.exists():
        raise FileExistsError("GGUF no caminho de destino não corresponde ao hash; não será sobrescrito.")
    download_verified(MODEL_URL,target,sha256=MODEL_SHA256,
                      exact_size=MODEL_BYTES,max_size=MODEL_BYTES)
    with target.open("rb") as stream:
        if stream.read(4)!=b"GGUF":
            target.unlink()
            raise ValueError("Modelo sem cabeçalho GGUF; arquivo recusado.")
    return "Qwen3-4B Q4_K_M instalado após SHA-256 e tamanho verificados."


def main()->int:
    parser=argparse.ArgumentParser(description="Instalar Qwen3-4B oficial para comparação GameDev")
    parser.add_argument("--confirm-download",action="store_true",help="Autoriza explicitamente download de 2,5 GB")
    args=parser.parse_args()
    print("Modelo: "+MODEL_FILENAME)
    print("Origem: Qwen/Qwen3-4B-GGUF @ "+MODEL_REVISION)
    print("Tamanho esperado: "+str(MODEL_BYTES)+" bytes")
    print("SHA-256 esperado: "+MODEL_SHA256)
    if not args.confirm_download:
        print("Somente inspeção; nenhum download sem --confirm-download.")
        return 0
    if os.name!="nt" or sys.maxsize<2**32:
        print("Instalação oferecida somente para Windows x64.")
        return 2
    try:
        print(install())
        return 0
    except (OSError,ValueError,FileExistsError) as exc:
        print("Download não concluído: "+type(exc).__name__,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
