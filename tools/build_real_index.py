#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.record_retrieval import RealKnowledgeIndex
def main():
    manifest=json.loads((ROOT/"brain_data/real_knowledge/semantic/manifest.json").read_text())
    index=RealKnowledgeIndex.build(manifest["records"]);stats=index.save(ROOT/"brain_data/real_knowledge/index/record-index.json.gz")
    (ROOT/"brain_data/real_knowledge/index/stats.json").write_text(json.dumps(stats,indent=2,sort_keys=True)+"\n")
    print(json.dumps(stats,sort_keys=True))
if __name__=="__main__":main()
