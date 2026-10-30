"""Safe, read-only Lua header audit for a local game folder.

This tool reads at most 4096 bytes per *.lua regular file. It does not
extract, decompile, decrypt, execute, copy, upload, or train on source files.
No file names, paths, text, sample bytes, secrets, or hashes enter the report.
The classifications describe *formats*, NOT legal permission for training.
Python 3.10+, standard library only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from inventory_local_data import is_link_or_junction

MAX_BYTES = 4096
MAX_ENTRIES = 200_000

def kind(sample: bytes, full_length: int) -> str:
    """Classify sample format without storing or reproducing any source text."""
    if not sample:
        return "empty"
    if sample.startswith(b"\x1bLua") or sample.startswith(b"\x1bLJ") or sample.startswith(b"\x1bKL"):
        return "compiled_lua_or_kl"
    if sample.startswith(b"\xef\xbb\xbf"):
        sample = sample[3:]
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            decoded = sample.decode("utf-16")
        except UnicodeDecodeError:
            return "undetermined_encoding"
        if any(c in decoded for c in ("\x00", "\ufffd")):
            return "binary_or_obfuscated"
        return "utf16_text_candidate"
    # Some historical files use UTF-16 without a BOM, so don't assume
    # that many NUL bytes means compilable Lua text.
    nulls = sample.count(b"\x00")
    if nulls > max(2, len(sample) // 15):
        return "binary_or_undetermined_utf16"
    controls = sum(b < 9 or (13 < b < 32) for b in sample)
    if controls > max(2, len(sample) // 25):
        return "binary_or_obfuscated"
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        # Older Lua scripts can use codepages. Do not guess.
        return "non_utf8_or_binary_unknown"
    if "\ufffd" in text:
        return "undetermined_encoding"
    if text.strip() == "":
        return "whitespace_only"
    # Header may stop in middle of a token; this is not a parser or proof.
    # Do not claim it is valid Lua code without syntax and behavior checks.
    return "utf8_text_candidate"

def analyze(folder: Path, *, max_entries: int=MAX_ENTRIES, peek: int=MAX_BYTES) -> dict:
    folder=Path(folder).expanduser()
    if not folder.is_dir() or is_link_or_junction(str(folder)):
        raise ValueError("Source directory not found or is a reparse link")
    if not (1 <= max_entries <= MAX_ENTRIES):
        raise ValueError("Invalid max_entries")
    if not (16 <= peek <= MAX_BYTES):
        raise ValueError("Peek limit must be 16..4096 bytes")
    counts=Counter(); sizes=Counter(); total=0; reads=0
    skipped=0; errors=0; dirs=0; partial=False
    def onerror(_):
        nonlocal errors
        errors += 1
    for root, subdirs, filenames in os.walk(folder, topdown=True, followlinks=False, onerror=onerror):
        safe=[]
        for subdir in subdirs:
            if is_link_or_junction(os.path.join(root,subdir)):
                skipped+=1
            else:
                safe.append(subdir)
        subdirs[:]=safe
        dirs+=len(safe)
        for filename in filenames:
            if not filename.lower().endswith(".lua"):
                continue
            filepath=os.path.join(root,filename)
            if is_link_or_junction(filepath):
                skipped+=1
                continue
            try:
                # Open only .lua, never execute it. Small read cap.
                with open(filepath,"rb") as stream:
                    head=stream.read(peek)
                    length=os.fstat(stream.fileno()).st_size
                classification=kind(head,length)
            except OSError:
                errors+=1
                continue
            reads+=1
            counts[classification]+=1
            sizes[classification]+=length
            total+=length
            if reads >= max_entries:
                partial=True
                subdirs[:]=[]
                break
        if partial:
            break
    return {
        "schema":"luna-lua-format-audit-v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "scope":"local read-only aggregate format sampling (maximum 4096 bytes per Lua file)",
        "lua_files_sampled":reads,"lua_bytes_total_metadata":total,
        "subdirectories_traversed":dirs,
        "sampled_content_bytes_upper_bound":reads*peek,
        "counts":[{"format":fmt,"files":num,"total_file_bytes":sizes[fmt]}
                  for fmt,num in sorted(counts.items(),key=lambda p:(-p[1],p[0]))],
        "errors":errors,"skipped_links":skipped,"partial":partial,
        "filenames_saved":False,"paths_saved":False,"source_text_saved":False,
        "file_hashes_saved":False,"files_copied_or_uploaded":0,
        "programs_executed":0,"files_transferred_to_training":0,
        "training_permission_approved":False,
        "notes":[
            "This is a sampled header/encoding check, not a Lua syntax parser.",
            "Readable text is not evidence of valid code or permission to train.",
            "Lua scripts extracted from a commercial game may still be protected.",
            "This tool never opens .bak, .exe, .dll, .kom, .rar, .7z or assets.",
            "Keep all reports locally. Do not share copyrighted scripts or private data."
        ],
    }

def main() -> None:
    parser=argparse.ArgumentParser(description="Local Lua format audit. No code copied or trained.")
    parser.add_argument("folder",type=Path)
    parser.add_argument("--out",type=Path,default=Path(__file__).resolve().parent/"reports"/"lua_format_audit.json")
    parser.add_argument("--max-entries",type=int,default=MAX_ENTRIES)
    args=parser.parse_args()
    dest=args.out.resolve()
    source=args.folder.resolve()
    if dest==source or source in dest.parents:
        raise ValueError("Refusing to save a report within the source folder")
    if dest.exists():
        raise FileExistsError("Report exists; provide a different --out path")
    report=analyze(args.folder,max_entries=args.max_entries)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print("No code exported and no model trained.")
if __name__=="__main__":
    main()
