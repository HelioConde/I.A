#!/usr/bin/env python3
"""Install modern official Windows llama.cpp GameDev runtime separately.

The frozen Brain-SSD research runtime and regular Luna chat binaries remain
untouched. The downloaded ZIP must match GitHub release SHA256, and each
executable/DLL must pass safe archive validation before extraction.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path,PurePosixPath
import shutil
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TAG="b11946"
ZIP_URL="https://github.com/ggml-org/llama.cpp/releases/download/"+TAG+"/llama-"+TAG+"-bin-win-cpu-x64.zip"
ZIP_SHA256="8a702bb07c873b133c56eb3acd92a48d7c5c9ad339c6435eddc5185e46e1a043"
DEST=Path("third_party/llama.cpp/ornith-gamedev-win-cpu-x64")
ZIP_SIZE_LIMIT=80*1024*1024
UNPACK_LIMIT=350*1024*1024


def safe_members(z:zipfile.ZipFile)->dict[str,zipfile.ZipInfo]:
    files:dict[str,zipfile.ZipInfo]={}
    total=0
    for info in z.infolist():
        if info.is_dir():continue
        name=info.filename.replace("\\","/")
        pieces=PurePosixPath(name).parts
        if name.startswith("/") or any(p in ("","..") for p in pieces) or ":" in name:
            raise ValueError("Unsafe archive pathname")
        base=pieces[-1].casefold()
        if not base.endswith((".exe",".dll")):
            continue
        if len(base)>160 or info.file_size>100*1024*1024:
            raise ValueError("Oversized binary")
        if base in files:
            raise ValueError("Duplicate native binary")
        total+=info.file_size
        if total>UNPACK_LIMIT or len(files)>150:
            raise ValueError("Archive expanded beyond safe bounds")
        files[base]=info
    if "llama-cli.exe" not in files:
        raise ValueError("Windows CPU runtime missing llama-cli.exe")
    return files

def install_archive(archive:Path,root:Path=ROOT)->Path:
    output=root/DEST
    if output.exists():
        raise FileExistsError("Dedicated GameDev runtime already exists; not overwritten.")
    output.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=".ornith-cli-staging-",dir=output.parent))
    try:
        with zipfile.ZipFile(archive) as z:
            entries=safe_members(z)
            for name,info in entries.items():
                with z.open(info) as src, (staging/name).open("xb") as dst:
                    shutil.copyfileobj(src,dst,length=1024*1024)
        os.replace(staging,output)
        return output/"llama-cli.exe"
    finally:
        if staging.exists():shutil.rmtree(staging)

def install(root:Path=ROOT)->Path:
    from install_windows_chat import download_verified
    existing=root/DEST/"llama-cli.exe"
    if existing.is_file():
        return existing
    if (root/DEST).exists():
        raise FileExistsError("Incomplete GameDev runtime; refuse overwrite.")
    with tempfile.TemporaryDirectory(prefix="ornith-runtime-") as t:
        zip_path=Path(t)/"llama-runtime.zip"
        download_verified(ZIP_URL,zip_path,sha256=ZIP_SHA256,max_size=ZIP_SIZE_LIMIT)
        if hashlib.sha256(zip_path.read_bytes()).hexdigest()!=ZIP_SHA256:
            raise ValueError("Runtime archive hash mismatch")
        return install_archive(zip_path,root)

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--confirm-download",action="store_true")
    a=p.parse_args()
    print("Modern official llama.cpp GameDev runtime:",TAG)
    print("Official release:",ZIP_URL)
    print("SHA-256:",ZIP_SHA256)
    print("Separate destination:",ROOT/DEST)
    if not a.confirm_download:
        print("Dry run only. Explicit --confirm-download required.")
        return 0
    if os.name!="nt" or sys.maxsize<2**32:
        print("Windows x64 only; installation refused.",file=sys.stderr)
        return 2
    try:
        print("Validated runtime:",install())
        return 0
    except (OSError,ValueError,FileExistsError,zipfile.BadZipFile) as exc:
        print("Runtime install failed:",type(exc).__name__,file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
