"""Private metadata-only inventory of a local game archive for Luna Forge.

NO file contents, extraction, hashing, executable execution, training, uploading
or data export. Results include only aggregate counts by extension/category.
Windows junctions and symbolic links are skipped. stdlib-only Python.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

ARCHIVES={".rar",".7z",".zip",".tar",".gz",".iso",".cab"}
DATABASE={".bak",".sql",".db",".sqlite",".sqlite3",".mdb",".mdf",".ldf"}
EXECUTABLES={".exe",".dll",".sys",".ocx",".com",".bat",".cmd",".ps1",".msi",".pyd"}
GAME_ASSETS={".kom",".p3m",".frm",".dds",".png",".jpg",".jpeg",".webp",".tga",
             ".ogg",".wav",".mp3",".mp4",".avi",".stg",".kstg",".mp3",".ttf",".ttc",".otf"}
POSSIBLE_CODE={".gd",".js",".jsx",".ts",".tsx",".py",".cs",".cpp",".cc",".c",".h",
               ".hpp",".java",".lua",".gdshader",".glsl",".rs",".go"}
DOCUMENTS={".txt",".md",".json",".xml",".ini",".cfg",".yml",".yaml",".html",".htm",
           ".csv",".log",".toml",".properties",".sln",".csproj"}
MAX_ENTRIES=200_000

def category(ext: str)->str:
    if ext in DATABASE: return "sensitive_database_backup"
    if ext in EXECUTABLES: return "do_not_execute_binary_or_script"
    if ext in ARCHIVES: return "closed_archive_not_processed"
    if ext in GAME_ASSETS: return "commercial_game_assets_do_not_train"
    if ext in POSSIBLE_CODE: return "possible_code_permission_review_required"
    if ext in DOCUMENTS: return "document_or_config_review_required"
    return "unknown_or_other"

def is_link_or_junction(path: str)->bool:
    # Avoid following symlinks, NTFS junctions, and other Windows reparse points.
    try:
        info=os.lstat(path)
    except OSError:
        return True
    return bool(stat.S_ISLNK(info.st_mode) or (
        getattr(info,"st_file_attributes",0) & getattr(stat,"FILE_ATTRIBUTE_REPARSE_POINT",1024)
    ))

def inspect(folder: Path,max_entries: int=MAX_ENTRIES)->dict:
    folder=Path(folder).expanduser()
    if not folder.is_dir() or is_link_or_junction(str(folder)):
        raise ValueError("Source folder is missing, inaccessible or a reparse link")
    if max_entries<1 or max_entries>MAX_ENTRIES:
        raise ValueError("Invalid inventory limit")
    counts=Counter(); bytes_by_category=Counter(); extensions=Counter()
    folders=0; files=0; total_bytes=0; skipped=0; errors=0; partial=False
    def onerror(_error):
        nonlocal errors
        errors+=1
    for root,dirs,names in os.walk(folder,topdown=True,followlinks=False,onerror=onerror):
        kept=[]
        for name in dirs:
            if is_link_or_junction(os.path.join(root,name)):
                skipped+=1
            else:
                kept.append(name)
        dirs[:]=kept
        folders+=len(kept)
        for name in names:
            path=os.path.join(root,name)
            if is_link_or_junction(path):
                skipped+=1
                continue
            try:
                length=os.stat(path,follow_symlinks=False).st_size
            except OSError:
                errors+=1
                continue
            ext=Path(name).suffix.lower() or "(sem extensao)"
            group=category(ext)
            extensions[ext]+=1
            counts[group]+=1
            bytes_by_category[group]+=length
            files+=1; total_bytes+=length
            if files>=max_entries:
                partial=True
                dirs[:]=[]
                break
        if partial:
            break
    return {
      "schema":"luna-local-inventory-v1",
      "created_utc":datetime.now(timezone.utc).isoformat(),
      "scope":"private metadata counts only; no paths or filenames saved",
      "files":files,"subdirectories":folders,"total_bytes":total_bytes,
      "extensions":[{"extension":ext,"files":qty} for ext,qty in sorted(extensions.items(),key=lambda p:(-p[1],p[0]))],
      "categories":[{"category":c,"files":qty,"total_bytes":bytes_by_category[c]}
                    for c,qty in sorted(counts.items(),key=lambda p:(-p[1],p[0]))],
      "skipped_links":skipped,"errors":errors,"partial":partial,
      "raw_commercial_content_training_approved":False,
      "files_copied_or_uploaded":0,
      "files_opened_or_executed":0,
      "notes":[
       "Database backups may contain accounts, passwords and personal information; never upload or train on them.",
       "Game clients, media, protected assets, decrypted material and binaries are NOT training data.",
       "Possible code is NOT automatically licensed: inspect provenance and rights before any training.",
       "The Luna GameCoder train_github.py script does NOT consume this report as training data."
      ]
    }

def main():
    ap=argparse.ArgumentParser(description="Private, read-only filename-extension inventory")
    ap.add_argument("folder",type=Path)
    ap.add_argument("--out",type=Path,default=Path(__file__).parent/"reports"/"local_data_inventory.json")
    ap.add_argument("--max-entries",type=int,default=MAX_ENTRIES)
    args=ap.parse_args()
    if args.out.resolve().is_relative_to(args.folder.resolve()):
        raise ValueError("Report must be outside the source folder")
    result=inspect(args.folder,args.max_entries)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists():
        raise FileExistsError("Existing report not overwritten; choose --out with a new name")
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    print("Private inventory saved locally. Nothing uploaded or trained.")

if __name__=="__main__":
    main()
