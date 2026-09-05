#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
targets=[
 "brain_data/real_knowledge/source-manifest.json",
 "brain_data/real_knowledge/sources/python-3.14-docs-text.zip",
 "brain_data/real_knowledge/sources/sqlite-doc-3530400.zip",
 "brain_data/real_knowledge/ingestion-summary.json",
 "brain_data/real_knowledge/semantic/brain.dat",
 "brain_data/real_knowledge/semantic/manifest.json",
 "brain_data/real_knowledge/random/brain.dat",
 "brain_data/real_knowledge/random/manifest.json",
 "brain_data/real_knowledge/index/record-index.json.gz",
 "brain_data/real_knowledge/index/stats.json",
 "benchmarks/data/phase4d_real_qa.json",
 "results/phase4d/retrieval-only.json",
 "results/phase4d/end-to-end.json",
 "results/phase4d/disk-accounting.json",
 "results/phase4d/SUMMARY.md",
 "docs/REAL_KNOWLEDGE.md",
 "docs/END_TO_END_MVP.md",
]
disk={"schema_version":1,"knowledge_tree_bytes":sum(p.stat().st_size for p in (ROOT/"brain_data/real_knowledge").rglob("*") if p.is_file()),
      "model_bytes":(ROOT/"models/Qwen3-0.6B-Q8_0.gguf").stat().st_size,
      "index_serialized_bytes":(ROOT/"brain_data/real_knowledge/index/record-index.json.gz").stat().st_size,
      "semantic_brain_bytes":(ROOT/"brain_data/real_knowledge/semantic/brain.dat").stat().st_size,
      "random_brain_bytes":(ROOT/"brain_data/real_knowledge/random/brain.dat").stat().st_size}
(ROOT/"results/phase4d/disk-accounting.json").write_text(json.dumps(disk,indent=2,sort_keys=True)+"\n")
rows=[]
for relative in targets:
 path=ROOT/relative
 if not path.is_file():raise FileNotFoundError(relative)
 rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}")
(ROOT/"results/phase4d-checksums.sha256").write_text("\n".join(rows)+"\n")
print(json.dumps(disk,sort_keys=True))
