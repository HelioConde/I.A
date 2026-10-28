"""Stage-2 private Lua format audit for the Elsword client directory.

For local diagnostics ONLY: read up to 4 KiB of regular *.lua files,
classify headers, never save source, filenames, hashes or paths, never execute
or train. Do not descend into HShield, database, backup, credential folders,
even when nested beneath the selected root. No network or dependencies.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

from analyze_local_lua import kind, MAX_BYTES
from train_private_lua import SKIP_PATH_PARTS, no_links, check_root

MAX_ENTRIES=200000
EXTRA_BLOCKED=frozenset(("logs","accounts","payment","payments","passwords","keys"))

def inspect(root: Path, *, max_entries: int=MAX_ENTRIES) -> dict:
    folder=check_root(root)
    if folder.name.casefold()!="elsword":
        raise ValueError("Expected explicitly selected Elsword folder, not a drive root or anti-cheat path")
    if not 1<=max_entries<=MAX_ENTRIES:
        raise ValueError("Invalid file limit")

    formats=Counter()
    format_bytes=Counter()
    visited=0
    content_bytes=0
    excluded_dirs=0
    links=0
    errors=0
    under_256=0
    partial=False
    def onerror(_):
        nonlocal errors
        errors+=1

    for current,dirs,files in os.walk(folder,topdown=True,followlinks=False,onerror=onerror):
        permitted=[]
        for name in dirs:
            child=Path(current)/name
            if not no_links(child):
                links+=1
            elif name.casefold() in SKIP_PATH_PARTS|EXTRA_BLOCKED:
                excluded_dirs+=1
            else:
                permitted.append(name)
        dirs[:]=permitted
        for name in files:
            if not name.casefold().endswith(".lua"):
                continue
            if visited>=max_entries:
                partial=True
                dirs[:]=[]
                break
            path=Path(current)/name
            if not no_links(path):
                links+=1
                continue
            try:
                metadata=os.stat(path,follow_symlinks=False)
                if not stat.S_ISREG(metadata.st_mode):
                    continue
                # No non-Lua content is opened. No output includes source.
                with path.open("rb") as f:
                    header=f.read(MAX_BYTES)
                fmt=kind(header,metadata.st_size)
            except OSError:
                errors+=1
                continue
            visited+=1
            content_bytes+=len(header)
            under_256+=int(metadata.st_size<256)
            formats[fmt]+=1
            format_bytes[fmt]+=metadata.st_size
        if partial:
            break

    return {
      "schema":"luna-elsword-lua-header-audit-v1",
      "created_utc":datetime.now(timezone.utc).isoformat(),
      "scope":"explicit local Elsword directory; up to 4 KiB per Lua",
      "lua_files_sampled":visited,
      "classification_counts":dict(sorted(formats.items())),
      "classification_metadata_bytes":dict(sorted(format_bytes.items())),
      "files_under_256_bytes":under_256,
      "sampled_bytes_read":content_bytes,
      "per_file_limit_bytes":MAX_BYTES,
      "excluded_sensitive_subdirectories":excluded_dirs,
      "links_skipped":links,
      "errors":errors,
      "partial":partial,
      "file_paths_or_names_saved":False,
      "source_text_saved":False,
      "files_uploaded_or_copied":0,
      "files_executed":0,
      "training_started":False,
      "weights_changed":False,
      "training_permission_inferred":False,
      "interpretation":[
        "UTF-8 text candidate is a HEADER format only, not proof of valid Lua.",
        "This audit does not verify ownership or rights to train on commercial scripts.",
        "This tool never trains Luna or exposes source code.",
        "Further training needs explicit authorization and a separately approved source scope.",
      ],
    }

def main():
    p=argparse.ArgumentParser(description="Local aggregate Lua header format audit, no training")
    p.add_argument("--source",type=Path,default=Path.home()/"Documents"/"grand chase files"/"Elsword")
    p.add_argument("--max-entries",type=int,default=MAX_ENTRIES)
    args=p.parse_args()
    print(json.dumps(inspect(args.source,max_entries=args.max_entries),
                     ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
