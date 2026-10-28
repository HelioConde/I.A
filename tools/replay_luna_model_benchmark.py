#!/usr/bin/env python3
"""Replay genuine archived model source. This NEVER calls inference or repairs code.

Original Qwen and Ornith attempts from GitHub run 40653494692 were falsely
marked JS syntax failures because llama-cli's interactive banner was evaluated
as code. Extract only original generated text and run syntax/browser gates.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from benchmark_luna_game_models import clean,syntax_valid

SOURCE_RUN=40653494692
LABELS=("ornith-1.5-9b","qwen3-4b")
HTML="""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Isolated original model candidate QA</title></head>
<body style="margin:0;background:#0e1425;color:white;overflow-x:hidden">
<canvas id="game" width="800" height="480" style="display:block;width:100%;max-width:800px;height:auto"></canvas>
<script src="game.js" defer></script></body></html>
"""


def replay(raw_dir:Path,dest:Path,label:str)->dict:
    if label not in LABELS:raise ValueError("unrecognized_model")
    report=json.loads((raw_dir/"provenance.json").read_text(encoding="utf-8"))
    if report.get("model")!=label or report.get("benchmark")!="Luna native GameDev v4":
        raise ValueError("provenance_model_mismatch")
    if report.get("model_sha256") is None or len(report["model_sha256"])!=64:
        raise ValueError("missing_original_model_sha256")
    dest.mkdir(parents=True,exist_ok=True)
    results=[]
    for attempt in (1,2):
        raw_file=raw_dir/("attempt-"+str(attempt)+".raw.txt")
        if not raw_file.is_file():
            results.append({"attempt":attempt,"status":"MISSING_RAW","playable":False})
            continue
        raw=raw_file.read_text(encoding="utf-8")
        original_sha=hashlib.sha256(raw.encode("utf-8")).hexdigest()
        try:
            source=clean(raw)
            if not syntax_valid(source):
                raise ValueError("javascript_syntax_error")
            path=dest/("attempt-"+str(attempt))
            path.mkdir(exist_ok=True)
            (path/"game.js").write_bytes(source.encode("utf-8"))
            (path/"index.html").write_text(HTML,encoding="utf-8")
            results.append({"attempt":attempt,"status":"VALID_JS_PENDING_BROWSER",
                            "playable":None,"original_raw_sha256":original_sha,
                            "extracted_source_sha256":hashlib.sha256(source.encode("utf-8")).hexdigest(),
                            "model_authored_js":True,"assistant_gameplay_code_used":False})
        except ValueError as exc:
            results.append({"attempt":attempt,"status":str(exc),"playable":False,
                            "original_raw_sha256":original_sha})
    info={"run_id":SOURCE_RUN,"model":label,"model_sha256":report["model_sha256"],
          "original_report_status":report["status"],
          "source": "archived real llama.cpp model attempts",
          "provenance_replayed_not_regenerated":True,"attempts":results,
          "gameplay_verified":False}
    (dest/"replay.json").write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return info


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--raw-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--label",choices=LABELS,required=True)
    a=p.parse_args()
    report=replay(a.raw_dir,a.out,a.label)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
