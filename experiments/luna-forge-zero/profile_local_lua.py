"""Private local structural profile for Lua: aggregates only, no source export.

For each regular .lua file inspect at most 64 KiB. Token counters are lexical
approximations, NOT a Lua parser, proof of valid Lua, or license verification.
Never execute, extract, decompile, upload or train on the files.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from inventory_local_data import is_link_or_junction
from analyze_local_lua import kind

MAX_BYTES = 65536
MAX_ENTRIES = 200000
KEYWORDS = frozenset(("function","if","elseif","for","while","repeat","return",
                      "local","require","do","until","end","break","goto"))
# Match comments and strings BEFORE identifiers, so ordinary keywords inside
# strings and single-line comments are ignored. Long Lua brackets and malformed
# input can still make these counters approximate.
LEXICAL = re.compile(
    r"--\[(=*)\[.*?\]\1\]"
    r"|--[^\r\n]*"
    r"|\[(=*)\[.*?\]\2\]"
    r"|\"(?:\\.|[^\"\\])*\""
    r"|'(?:\\.|[^'\\])*'"
    r"|[A-Za-z_][A-Za-z0-9_]*",
    re.DOTALL,
)

def keyword_counts(text: str) -> Counter:
    result=Counter()
    for match in LEXICAL.finditer(text):
        token=match.group(0)
        if token in KEYWORDS:
            result[token]+=1
    return result

def structural_group(counts: Counter) -> str:
    functions=counts["function"] > 0
    decisions=any(counts[x] for x in ("if","for","while","repeat"))
    if functions and decisions: return "functions_and_control_flow"
    if functions: return "functions_only"
    if decisions: return "control_flow_only"
    return "no_detected_functions_or_control_flow"

def analyze(folder: Path, limit: int=MAX_ENTRIES, peek: int=MAX_BYTES) -> dict:
    folder=Path(folder).expanduser()
    if not folder.is_dir() or is_link_or_junction(str(folder)):
        raise ValueError("Folder does not exist or is a junction/symlink")
    if not 1<=limit<=MAX_ENTRIES or not 4096<=peek<=MAX_BYTES:
        raise ValueError("Invalid scan limits")
    formats=Counter(); groups=Counter(); keywords=Counter()
    scanned=0; bytes_read=0; files_truncated=0; skipped=0; errors=0; partial=False
    def onerror(_):
        nonlocal errors
        errors+=1
    for root,dirs,files in os.walk(folder,topdown=True,followlinks=False,onerror=onerror):
        allowed=[]
        for name in dirs:
            if is_link_or_junction(os.path.join(root,name)): skipped+=1
            else: allowed.append(name)
        dirs[:]=allowed
        for name in files:
            if not name.lower().endswith(".lua"):
                continue
            path=os.path.join(root,name)
            if is_link_or_junction(path):
                skipped+=1
                continue
            try:
                with open(path,"rb") as stream:
                    sample=stream.read(peek)
                    length=os.fstat(stream.fileno()).st_size
            except OSError:
                errors+=1
                continue
            scanned+=1; bytes_read+=len(sample)
            if length>peek: files_truncated+=1
            fmt=kind(sample[:4096],length)
            formats[fmt]+=1
            if fmt=="utf8_text_candidate":
                tokens=keyword_counts(sample.decode("utf-8",errors="ignore"))
                keywords.update(tokens)
                groups[structural_group(tokens)]+=1
            if scanned>=limit:
                partial=True
                dirs[:]=[]
                break
        if partial: break
    return {
       "schema":"luna-lua-structural-aggregate-v1",
       "created_utc":datetime.now(timezone.utc).isoformat(),
       "scope":"local, sample only; aggregate statistics; not syntax or licensing validation",
       "lua_files_sampled":scanned,
       "sampled_bytes_read":bytes_read,
       "max_bytes_per_file":peek,
       "files_larger_than_sample":files_truncated,
       "format_counts":dict(sorted(formats.items())),
       "structure_groups":dict(sorted(groups.items())),
       "lexical_keyword_occurrences":dict(sorted(keywords.items())),
       "errors":errors,"skipped_links":skipped,"partial":partial,
       "filenames_saved":False,"source_saved":False,"file_paths_saved":False,
       "files_exported":0,"files_executed":0,"files_trained":0,
       "training_permission_approved":False,
       "interpretation":[
          "A matching token is not evidence of valid Lua syntax or game mechanics.",
          "Counts reflect only the first part of large files, may omit later constructs.",
          "This report does not grant a license to train on game scripts.",
          "Original gameplay tasks and permissively licensed sources remain separate."
       ],
    }

def main():
    parser=argparse.ArgumentParser(description="Private local Lua lexical summary, no source export")
    parser.add_argument("folder",type=Path)
    parser.add_argument("--out",type=Path,default=Path(__file__).resolve().parent/"reports"/"lua_structure.json")
    parser.add_argument("--max-entries",type=int,default=MAX_ENTRIES)
    parser.add_argument("--peek",type=int,default=MAX_BYTES)
    args=parser.parse_args()
    dest=args.out.resolve()
    source=args.folder.resolve()
    if dest==source or source in dest.parents:
        raise ValueError("Report cannot be written inside input folder")
    if dest.exists():
        raise FileExistsError("Report already exists; choose another --out")
    result=analyze(args.folder,limit=args.max_entries,peek=args.peek)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print("No scripts copied, uploaded or used for training.")

if __name__=="__main__":
    main()
