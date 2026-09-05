#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.real_knowledge import ingest_sources,pack_records

def main():
    base=ROOT/"brain_data/real_knowledge"; records,stats=ingest_sources(base,base/"source-manifest.json")
    layouts={name:pack_records(records,base/name,name) for name in ("semantic","random")}
    payload={"schema_version":1,"ingestion":stats,"layouts":{name:manifest["stats"]|{"page_count":manifest["page_count"],"corpus_size_bytes":manifest["corpus_size_bytes"]} for name,manifest in layouts.items()}}
    (base/"ingestion-summary.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print(json.dumps(payload,sort_keys=True))
if __name__=="__main__":main()
