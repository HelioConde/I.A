#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
targets=[
 "results/phase4e/STATUS.md",
 "results/phase4e/preparation/phase4d-freeze-manifest.json",
 "results/phase4e/preparation/preparation-environment.json",
 "results/phase4e/preparation/preparation-status.json",
 "results/phase4e/preparation/runner-audit.json",
 "docs/PHYSICAL_END_TO_END.md",
 "src/brain_ssd/physical_validation.py",
 "tools/prepare_physical_validation.py",
 "tools/run_physical_end_to_end_validation.py",
 "tests/test_phase4e_physical_validation.py",
]
rows=[]
for relative in targets:
 path=ROOT/relative
 if not path.is_file():raise FileNotFoundError(relative)
 rows.append({"path":relative,"bytes":path.stat().st_size,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
payload={"schema_version":1,"scope":"PHASE4E_PREPARATION_ONLY","physical_results_included":False,"files":rows}
(ROOT/"results/phase4e/preparation-checksums.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
print(json.dumps({"files":len(rows),"physical_results_included":False},sort_keys=True))
