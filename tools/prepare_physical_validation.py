#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,platform,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.physical_validation import physical_audit,verify_checksum_manifest

FREEZE_FILES=["results/phase4d-checksums.sha256","tools/ingest_real_knowledge.py","tools/build_real_index.py","tools/run_phase4d.py",
              "benchmarks/data/phase4d_real_qa.json","models/Qwen3-0.6B-Q8_0.gguf"]+[str(p.relative_to(ROOT)) for p in sorted((ROOT/"src/brain_ssd").glob("*.py"))]

def digest(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def main()->int:
    output=ROOT/"results/phase4e/preparation";output.mkdir(parents=True,exist_ok=True)
    phase_checks=[]
    for manifest in sorted((ROOT/"results").glob("*checksums.sha256")):
        if "phase4e" not in manifest.name:phase_checks.append(verify_checksum_manifest(ROOT,manifest))
    try:parent_commit=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    except (subprocess.CalledProcessError,FileNotFoundError):parent_commit=None
    freeze={"schema_version":2,"freeze_id":"BRAIN_SSD_PHASE4D_FROZEN_2026-08-07","created_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
            "parent_repository_commit_context":parent_commit,"git_tag_created":False,
            "git_tag_reason":"Parent .git is outside the authorized Brain-SSD directory; in-scope cryptographic manifest used instead.",
            "phase4d_checksum_manifest_sha256":digest(ROOT/"results/phase4d-checksums.sha256"),
            "llama_cpp_source_commit":"217df17ac30ba2a8c374088772f81926cc5beee3",
            "llama_completion_binary_sha256_reference":"d4a4e7371d4aaa5f064f83549f074b69713b7aadf27b0a92dbc4ce40b069b4fe",
            "files":{relative:digest(ROOT/relative) for relative in FREEZE_FILES},
            "frozen_configuration":{"model":"Qwen3-0.6B-Q8_0.gguf","runtime":"llama.cpp","device":"none","threads":4,"ctx_size":4096,
              "n_predict":96,"temperature":0,"logical_page_bytes":1048576,"storage_extent_bytes":4194304,"storage_access":"logical-only",
              "residency":"KernelOnly","cognitive_cache":"shadow","madv_cold":False,"madv_pageout":False,"prefetch":False,"context_budget_tokens":2048}}
    freeze_path=output/"phase4d-freeze-manifest.json"
    if freeze_path.exists():
        frozen=json.loads(freeze_path.read_text())
        mismatches=[relative for relative,expected in frozen["files"].items() if not (ROOT/relative).is_file() or digest(ROOT/relative)!=expected]
        if mismatches:raise SystemExit(f"FROZEN_ARTIFACT_MISMATCH: {mismatches}")
        # Schema 1 already anchored the critical 4D files. Enrich it once with
        # every core module so transferred runs cannot silently mix code.
        if frozen.get("schema_version",1)<2:
            frozen["schema_version"]=2;frozen["files"].update(freeze["files"]);freeze_path.write_text(json.dumps(frozen,indent=2,sort_keys=True)+"\n")
        freeze=frozen
    else:
        freeze_path.write_text(json.dumps(freeze,indent=2,sort_keys=True)+"\n")
    audit=physical_audit(ROOT);audit["purpose"]="PREPARATION_ONLY_NOT_PHYSICAL_RESULT"
    (output/"preparation-environment.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n")
    dependencies={name:{"path":str(path),"exists":path.exists()} for name,path in {
        "model":ROOT/"models/Qwen3-0.6B-Q8_0.gguf","llama_completion":ROOT/"build/llama.cpp/bin/llama-completion",
        "semantic_brain":ROOT/"brain_data/real_knowledge/semantic/brain.dat","index":ROOT/"brain_data/real_knowledge/index/record-index.json.gz"}.items()}
    status={"schema_version":1,"python":platform.python_version(),"all_previous_checksums_ok":all(item["ok"] for item in phase_checks),
            "checksum_manifests":phase_checks,"dependencies":dependencies,"ready_for_transfer":all(item["exists"] for item in dependencies.values()) and all(item["ok"] for item in phase_checks),
            "physical_matrix_executed":False}
    (output/"preparation-status.json").write_text(json.dumps(status,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"ready_for_transfer":status["ready_for_transfer"],"freeze_id":freeze["freeze_id"],"environment_type":audit["environment_type"]},sort_keys=True))
    return 0 if status["ready_for_transfer"] else 1
if __name__=="__main__":raise SystemExit(main())
