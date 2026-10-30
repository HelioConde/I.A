"""Private local directory-category audit: metadata only, never file content.

Counts .lua files in permitted and excluded directory trees without opening
any files, following reparse points, reporting paths/names, or changing any
training allow/deny rules. No user data leaves the machine.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

from train_private_lua import SKIP_PATH_PARTS, check_root, no_links

MAX_ENTRIES = 200000
SENSITIVE_NAMES = frozenset((
    "database","databases","backup","backups","billing",
    "account","accounts","users","user","credentials","secrets",
    "authentication","auth","private",
))
GAME_NAMES = frozenset(("elsword","hshield"))
CATEGORIES = ("permitted", "game_or_client_excluded",
              "sensitive_or_backup_excluded", "repository_metadata_excluded")

def excluded_category(name: str) -> str:
    if name.lower() in GAME_NAMES:
        return "game_or_client_excluded"
    if name.lower() in SENSITIVE_NAMES:
        return "sensitive_or_backup_excluded"
    return "repository_metadata_excluded"

def audit(folder: Path, max_entries: int=MAX_ENTRIES) -> dict:
    root=check_root(folder)
    if not 1<=max_entries<=MAX_ENTRIES:
        raise ValueError("Invalid entry limit")
    counts={kind:Counter() for kind in CATEGORIES}
    scope_for={str(root):"permitted"}
    excluded_roots=Counter()
    errors=0
    linked=0
    walked=0
    partial=False

    def onerror(_exc):
        nonlocal errors
        errors+=1

    for current, dirs, names in os.walk(root,topdown=True,followlinks=False,onerror=onerror):
        scope=scope_for.pop(str(current),"permitted")
        counts[scope]["directories_visited"]+=1
        safe_dirs=[]
        for name in dirs:
            candidate=Path(current)/name
            if not no_links(candidate):
                linked+=1
                continue
            next_scope=scope
            if scope=="permitted" and name.lower() in SKIP_PATH_PARTS:
                next_scope=excluded_category(name)
                excluded_roots[next_scope]+=1
            scope_for[str(candidate)]=next_scope
            safe_dirs.append(name)
        dirs[:]=safe_dirs
        for name in names:
            walked+=1
            if walked>max_entries:
                partial=True
                dirs[:]=[]
                break
            if not name.lower().endswith(".lua"):
                continue
            candidate=Path(current)/name
            if not no_links(candidate):
                linked+=1
                continue
            try:
                info=os.stat(candidate,follow_symlinks=False)
            except OSError:
                errors+=1
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            counts[scope]["lua_files"]+=1
            counts[scope]["lua_bytes_metadata"]+=info.st_size
        if partial:
            break

    groups={scope:{
        "lua_files":counts[scope]["lua_files"],
        "lua_bytes_metadata":counts[scope]["lua_bytes_metadata"],
        "directories_visited":counts[scope]["directories_visited"],
    } for scope in CATEGORIES}
    total=sum(entry["lua_files"] for entry in groups.values())
    excluded=sum(entry["lua_files"] for key,entry in groups.items() if key!="permitted")
    return {
        "schema":"luna-private-lua-directory-audit-v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "scope":"local metadata-only audit; does not open or read file contents",
        "lua_files_counted":total,
        "lua_files_under_protected_directories":excluded,
        "protected_root_counts":{key:excluded_roots[key] for key in CATEGORIES if key!="permitted"},
        "scope_counts":groups,
        "non_lua_filenames_examined_only_in_memory":True,
        "directory_links_and_file_links_skipped":linked,
        "metadata_errors":errors,
        "partial":partial,
        "path_names_or_source_saved":False,
        "file_contents_read":0,
        "files_executed_or_copied":0,
        "network_calls":0,
        "training_started":False,
        "model_weights_changed":False,
        "permission_to_train_inferred":False,
        "notes":[
            "Excluded directories were traversed FOR METADATA COUNTS ONLY.",
            "The private Lua trainer will continue to exclude these directories.",
            "Lua inside a commercial client or backups is not automatically approved for training.",
            "The report includes no filenames or paths and must not be treated as a license or validation of script contents.",
        ],
    }

def main():
    p=argparse.ArgumentParser(description="Count Lua in excluded folders; metadata only, no training")
    p.add_argument("folder",type=Path)
    p.add_argument("--max-entries",type=int,default=MAX_ENTRIES)
    args=p.parse_args()
    result=audit(args.folder,args.max_entries)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result["partial"]:
        raise SystemExit(3)

if __name__=="__main__":
    main()
