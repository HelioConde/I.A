"""Identify explicitly excluded Lua roots for *local review only*.

This script never opens files or decides whether their contents are licensed.
Folder paths appear ONLY in the local user's terminal (never saved or sent).
No source text, filenames, credentials or model weights are read/written.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import os
import stat

from train_private_lua import SKIP_PATH_PARTS, check_root, no_links

GROUPS = {"elsword": "game_client", "hshield": "anti_cheat"}
RESTRICTED = frozenset(("hshield", "database", "databases", "backup", "backups",
                        "billing", "account", "accounts", "users", "user",
                        "credentials", "secrets", "authentication", "auth",
                        "private", ".git"))
MAX_ENTRIES = 200000

def count_lua_metadata(folder: Path, budget: int=MAX_ENTRIES) -> tuple[int,int,bool]:
    """Only stat() .lua files, never read/open. Skip reparse points."""
    total,bytes_meta,inspected=0,0,0
    partial=False
    for current, dirs, files in os.walk(folder,followlinks=False):
        dirs[:] = [d for d in dirs if no_links(Path(current)/d)
                   and d.lower() not in RESTRICTED]
        for f in files:
            inspected+=1
            if inspected>budget:
                partial=True
                dirs[:]=[]
                break
            if not f.lower().endswith(".lua"):
                continue
            item=Path(current)/f
            if not no_links(item):
                continue
            try:
                info=os.stat(item,follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                total+=1
                bytes_meta+=info.st_size
        if partial:
            break
    return total,bytes_meta,partial

def scopes(folder: Path) -> list[dict]:
    root=check_root(folder)
    selected=[]
    # Only discover excluded roots from the previously blocked directory names.
    for current,dirs,_ in os.walk(root,followlinks=False):
        kept=[]
        for name in dirs:
            child=Path(current)/name
            if not no_links(child):
                continue
            if name.lower() in SKIP_PATH_PARTS:
                category=GROUPS.get(name.lower(),"sensitive_or_other")
                if category in ("game_client","anti_cheat"):
                    count,bytes_meta,partial=count_lua_metadata(child)
                    selected.append({
                        "scope_id":len(selected)+1,
                        "local_directory_for_human_review":str(child),
                        "category":category,
                        "lua_files_metadata":count,
                        "lua_bytes_metadata":bytes_meta,
                        "partial":partial,
                        "training_permitted":False,
                    })
            else:
                kept.append(name)
        dirs[:]=kept
    return selected

def main():
    p=argparse.ArgumentParser(description="Show local client/game Lua roots for rights review")
    p.add_argument("--source",type=Path,required=True)
    args=p.parse_args()
    results=scopes(args.source)
    print("LOCAL directory review ONLY; paths shown here never leave this terminal.")
    print("No source files opened, no training, no rights inferred. HShield/anti-cheat remains excluded.")
    for entry in results:
        print(f"\nScope #{entry['scope_id']} [{entry['category']}]")
        print(" Directory (KEEP PRIVATE):",entry["local_directory_for_human_review"])
        print(" Lua files (metadata):",entry["lua_files_metadata"])
        print(" Byte sizes (metadata):",entry["lua_bytes_metadata"])
        print(" Partial:",entry["partial"])
    print(f"\nTotal excluded roots identified: {len(results)}")
    print("Before ANY training, review provenance/permissions. Do not move/rename to bypass filters.")

if __name__=="__main__":
    main()
