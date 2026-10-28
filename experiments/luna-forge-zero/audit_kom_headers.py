"""Safe LOCAL KOM archive inventory (metadata + fixed header only).

Inspect only paths ending .kom; at most 72 header bytes read per file.
Never decompress, decrypt, enumerate embedded names, extract, execute,
change, copy or upload archive contents. No network. Report ONLY aggregates.
KOG signatures and offsets apply to some KOM v0.2/v0.3 layouts; others
remain unknown instead of being guessed or treated as damaged.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import struct

from train_private_lua import check_root, no_links, SKIP_PATH_PARTS

MAX_ENTRIES=200000
MAX_READ=72
SKIP_DIRS=(SKIP_PATH_PARTS-{"elsword"})|frozenset(
    {"logs","keys","payments","payment","cache","temp","tmp"})
MAGIC=b"KOG GC TEAM MASSFILE V."

def classify_header(header: bytes, size: int) -> tuple[str,int|None]:
    """Identify known legacy versions; count only plausibly populated headers."""
    if len(header)<MAX_READ:
        return "unknown_or_too_short",None
    if not header.startswith(MAGIC):
        return "unknown_signature",None
    label=header[:52].split(b"\0",1)[0]
    version=None
    if b"V.0.2." in label:
        version="kog_kom_v0_2"
    elif b"V.0.3." in label:
        version="kog_kom_v0_3"
    if version is None:
        return "kog_kom_other_version",None
    count=struct.unpack_from("<I",header,52)[0]
    table_size=struct.unpack_from("<I",header,68)[0]
    # Header has one count and one metadata table size at these offsets
    # for legacy versions. This is just a sanity check, not a full parser.
    if size<72 or table_size>size-72 or count>1_000_000:
        return version+"_unverified_layout",None
    return version,count

def scan(folder: Path, *, max_entries:int=MAX_ENTRIES)->dict:
    root=check_root(folder)
    if not 1<=max_entries<=MAX_ENTRIES:
        raise ValueError("max_entries must be 1..200000")
    formats=Counter()
    files=0
    total_size=0
    header_bytes=0
    declared_sum=0
    count_known=0
    skipped_dirs=0
    skipped_links=0
    errors=0
    partial=False
    def onerror(_):
        nonlocal errors
        errors+=1
    for current,dirs,names in os.walk(root,topdown=True,followlinks=False,onerror=onerror):
        allowed=[]
        for name in dirs:
            child=Path(current)/name
            if not no_links(child):
                skipped_links+=1
            elif name.casefold() in SKIP_DIRS:
                skipped_dirs+=1
            else:
                allowed.append(name)
        dirs[:]=allowed
        for name in names:
            if not name.casefold().endswith(".kom"):
                continue
            if files>=max_entries:
                partial=True
                dirs[:]=[]
                break
            candidate=Path(current)/name
            if not no_links(candidate):
                skipped_links+=1
                continue
            try:
                info=os.stat(candidate,follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    continue
                with candidate.open("rb") as f:
                    header=f.read(MAX_READ)
                version,count=classify_header(header,info.st_size)
            except OSError:
                errors+=1
                continue
            files+=1
            total_size+=info.st_size
            header_bytes+=len(header)
            formats[version]+=1
            if count is not None:
                count_known+=1
                declared_sum+=count
        if partial:
            break
    return {
        "schema":"luna-local-kom-header-audit-v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "purpose":"locally count KOM archive metadata; no extraction or training",
        "kom_files_sampled":files,
        "total_kom_bytes_metadata":total_size,
        "header_bytes_read":header_bytes,
        "max_header_bytes_per_file":MAX_READ,
        "format_counts":dict(sorted(formats.items())),
        "archives_with_plausible_declared_item_counts":count_known,
        "declared_internal_item_count_sum_unverified":declared_sum,
        "declared_internal_lua_file_count":"UNKNOWN_NOT_INSPECTED",
        "protected_subdirectories_skipped":skipped_dirs,
        "links_skipped":skipped_links,
        "errors":errors,
        "partial":partial,
        "paths_or_filenames_saved":False,
        "archive_tables_read":False,
        "archive_payload_read":False,
        "files_extracted":0,
        "files_executed":0,
        "files_copied_or_uploaded":0,
        "network_requests":0,
        "training_started":False,
        "weights_changed":False,
        "training_rights_inferred":False,
        "notes":[
            "Only fixed-length headers were read. Inner file names and types were NOT inspected.",
            "Version and item counts may be absent/invalid in other proprietary KOM variants.",
            "The internal item count is not the number of Lua scripts; archives may contain assets.",
            "Commercial game archives are not automatically authorized as AI training data.",
        ],
    }

def main():
    p=argparse.ArgumentParser(description="Safe KOM inventory: max 72 bytes per .kom, no extraction")
    p.add_argument("--source",type=Path,default=Path.home()/"Documents"/"grand chase files")
    p.add_argument("--max-entries",type=int,default=MAX_ENTRIES)
    args=p.parse_args()
    print(json.dumps(scan(args.source,max_entries=args.max_entries),
                     ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
