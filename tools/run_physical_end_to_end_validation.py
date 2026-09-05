#!/usr/bin/env python3
"""Phase 4E native Debian runner. It refuses to label Codespace data as physical."""
from __future__ import annotations
import argparse,hashlib,json,re,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"tools"))
from brain_ssd.physical_validation import GIB,SystemSampler,classify_profile,counter_delta,fadvise_drop,file_residency,physical_audit,read_key_values,self_counters,verify_checksum_manifest
from brain_ssd.record_retrieval import ContextBuilder,RealKnowledgeIndex,build_prompt
from brain_ssd.telemetry import run_measured
from run_phase4d import QA_PATH,INDEX_PATH,MODEL_PATH,RUNTIME_PATH,clean_answer,evaluate_query,qwen_command,score_answer

PROFILE_DIR={"physical_native":"physical_native","target_8gb":"target_8gb","low_4gb":"low_4gb"}
CANONICAL_VARIANTS=("qwen_only","standard_retrieval","brain_ssd")

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def verify_freeze()->dict:
    path=ROOT/"results/phase4e/preparation/phase4d-freeze-manifest.json"
    if not path.exists():raise RuntimeError("run prepare_physical_validation.py first")
    freeze=json.loads(path.read_text());errors=[]
    for relative,expected in freeze["files"].items():
        actual=sha(ROOT/relative) if (ROOT/relative).is_file() else None
        if actual!=expected:errors.append({"path":relative,"expected":expected,"actual":actual})
    phase=verify_checksum_manifest(ROOT,ROOT/"results/phase4d-checksums.sha256")
    import subprocess
    source=subprocess.run(["git","-C",str(ROOT/"third_party/llama.cpp"),"rev-parse","HEAD"],text=True,capture_output=True,check=False).stdout.strip()
    if source!=freeze.get("llama_cpp_source_commit"):errors.append({"path":"third_party/llama.cpp","expected":freeze.get("llama_cpp_source_commit"),"actual":source})
    runtime_hash=sha(RUNTIME_PATH) if RUNTIME_PATH.is_file() else None
    version=subprocess.run([str(RUNTIME_PATH),"--version"],text=True,capture_output=True,check=False) if RUNTIME_PATH.is_file() else None
    runtime={"source_commit":source,"binary_sha256":runtime_hash,"reference_binary_sha256":freeze.get("llama_completion_binary_sha256_reference"),
             "binary_exact_match":runtime_hash==freeze.get("llama_completion_binary_sha256_reference"),"version_output":((version.stdout+version.stderr).strip() if version else None)}
    return {"ok":not errors and phase["ok"],"freeze_id":freeze["freeze_id"],"errors":errors,"phase4d":phase,"configuration":freeze["frozen_configuration"],"runtime_identity":runtime}

def prompt_for(variant:str,query:dict,context:dict)->str:
    if variant=="qwen_only":
        return ("Answer the technical question from your own internal knowledge. Answer concisely; if you do not know, reply exactly NO_KNOWLEDGE.\n\n"
                f"USER QUESTION:\n{query['query']}\n\nANSWER:\n/no_think")
    return build_prompt(query["query"],context)

def one_run(query:dict,variant:str,cache_state:str,index,records,drop:bool)->dict:
    brain_path=ROOT/"brain_data/real_knowledge/semantic/brain.dat"
    drop_result={};initial={}
    if drop:
        drop_result["model"]=fadvise_drop(MODEL_PATH)
        if variant!="qwen_only":drop_result["knowledge"]=fadvise_drop(brain_path)
    initial["model"]=file_residency(MODEL_PATH)
    if variant!="qwen_only":initial["knowledge"]=file_residency(brain_path)
    with SystemSampler(.05) as system:
        retrieval=None;knowledge_before=self_counters()
        if variant=="qwen_only":context={"text":"","estimated_tokens":0,"source_ids":[],"bytes":0}
        elif variant=="oracle":
            context=ContextBuilder(2048).build([records[rid] for rid in query["expected_record_ids"]])
        else:
            mode="standard" if variant=="standard_retrieval" else "brain"
            retrieval=evaluate_query(index,records,query,"semantic",mode,2048);context=retrieval["context"]
        knowledge_delta=counter_delta(knowledge_before,self_counters())
        measured=run_measured(qwen_command(prompt_for(variant,query,context)),sample_interval_s=.02)
    answer=clean_answer(measured["stdout"]);stderr=measured.pop("stderr");measured.pop("samples",None)
    prompt_match=re.search(r"prompt eval time\s*=.*?([0-9.]+) tokens per second",stderr,re.I|re.S)
    measured["metrics"]["prompt_tokens_per_second"]=float(prompt_match.group(1)) if prompt_match else None
    retrieval_ms=(retrieval or {}).get("timing_ms",{}).get("retrieval_total",0)
    return {"query_id":query["query_id"],"variant":variant,"cache_state":cache_state,"cold_classification":"COLD" if drop and initial["model"]["resident_ratio"]<.05 and (variant=="qwen_only" or initial["knowledge"]["resident_ratio"]<.05) else ("BEST_EFFORT_COLD" if drop else "WARM"),
            "drop":drop_result,"initial_residency":initial,"retrieval":retrieval,"answer":answer,"score":score_answer(answer,query,context["source_ids"]),
            "qwen":measured,"pipeline":{"retrieval_ms":retrieval_ms,"qwen_ms":measured["metrics"]["latency_ms"],"total_ms":retrieval_ms+measured["metrics"]["latency_ms"]},
            "knowledge_process":knowledge_delta,"system":system.summary(),"gpu_used":False,"device":"none"}

def aggregate(runs:list[dict],variants)->dict:
    output={}
    for variant in variants:
        for state in ("cold","warm"):
            rows=[r for r in runs if r["variant"]==variant and r["cache_state"]==state]
            if not rows:continue
            output[f"{variant}:{state}"]={"runs":len(rows),"quality_mean":statistics.mean(r["score"]["required_fact_score"] for r in rows),
              "ttft_median_ms":statistics.median(r["qwen"]["metrics"]["ttft_ms"] for r in rows),"latency_mean_ms":statistics.mean(r["qwen"]["metrics"]["latency_ms"] for r in rows),
              "generation_tps_mean":statistics.mean(r["qwen"]["metrics"]["tokens_per_second"] for r in rows if r["qwen"]["metrics"]["tokens_per_second"] is not None),
              "model_physical_read_bytes":sum(r["qwen"]["metrics"]["storage_read_bytes_process_total"] or 0 for r in rows),
              "knowledge_physical_read_bytes":sum(r["knowledge_process"].get("read_bytes") or 0 for r in rows),
              "model_major_faults":sum(r["qwen"]["metrics"]["major_page_faults"] or 0 for r in rows),"model_minor_faults":sum(r["qwen"]["metrics"]["minor_page_faults"] or 0 for r in rows),
              "knowledge_major_faults":sum(r["knowledge_process"].get("major_faults") or 0 for r in rows),"knowledge_minor_faults":sum(r["knowledge_process"].get("minor_faults") or 0 for r in rows),
              "router_mean_ms":statistics.mean((r["retrieval"] or {}).get("timing_ms",{}).get("routing",0) for r in rows),
              "storage_mean_ms":statistics.mean((r["retrieval"] or {}).get("timing_ms",{}).get("storage",0) for r in rows),
              "context_build_mean_ms":statistics.mean((r["retrieval"] or {}).get("timing_ms",{}).get("context_build",0) for r in rows),
              "pipeline_total_mean_ms":statistics.mean(r["pipeline"]["total_ms"] for r in rows),
              "active_brain_mean_bytes":statistics.mean((r["retrieval"] or {}).get("active_brain_bytes",0) for r in rows),
              "context_tokens_mean":statistics.mean((r["retrieval"] or {}).get("context",{}).get("estimated_tokens",0) for r in rows),
              "record_recall":sum((r["retrieval"] or {}).get("record_true_positive",0) for r in rows)/max(1,sum((r["retrieval"] or {}).get("record_expected",0) for r in rows)),
              "record_precision":sum((r["retrieval"] or {}).get("record_true_positive",0) for r in rows)/max(1,sum((r["retrieval"] or {}).get("record_retrieved",0) for r in rows)),
              "rss_peak_bytes":max(r["qwen"]["metrics"]["rss_bytes_max"] or 0 for r in rows),
              "pss_peak_bytes":max(r["qwen"]["metrics"]["pss_bytes_max"] or 0 for r in rows),"system_ram_used_peak_bytes":max(r["system"]["system_ram_used_peak_bytes"] or 0 for r in rows)}
    return output

def render_report(audit:dict,summary:dict)->str:
    rows=[]
    for key,value in summary["canonical"].items():
        rows.append(f"| {key} | {value.get('ttft_median_ms')} | {value.get('pipeline_total_mean_ms')} | {value.get('generation_tps_mean')} | {value.get('rss_peak_bytes')} | {value.get('pss_peak_bytes')} | {value.get('model_physical_read_bytes')} | {value.get('knowledge_physical_read_bytes')} |")
    storage=audit.get("storage",{});session=summary["session"]
    return "\n".join(["# Phase 4E physical validation report","",
      f"- Environment/profile: `{summary['environment_type']}` / `{summary['profile']}`",
      f"- Freeze: `{summary['freeze_id']}`; CPU-only: `--device none`; GPU used: **no**",
      f"- Hardware: {audit.get('cpu_count')} threads; {audit.get('physical_ram_total_bytes')} bytes RAM; kernel `{audit.get('kernel')}`; Debian `{audit.get('debian',{}).get('PRETTY_NAME')}`",
      f"- Storage: `{storage.get('storage_type')}` `{storage.get('model')}` via `{storage.get('interface')}`; filesystem audit is in `hardware.json`",
      f"- Swap used peak: {summary['swap_policy']['swap_used_peak_bytes']} bytes",
      "","## Canonical cold/warm matrix","",
      "| Variant:state | TTFT median ms | Pipeline total mean ms | Generation tok/s | RSS peak | PSS peak | Model physical bytes | Knowledge physical bytes |",
      "|---|---:|---:|---:|---:|---:|---:|---:|",*rows,"",
      "Router, storage and ContextBuilder timings; context tokens, Active Brain, recall, precision, file/page faults and system/page-cache peaks are retained per variant in `summary.json` and per answer in `raw-runs.json`.","",
      "## Sustained session and decision","",
      f"- Runs/duration: {session['runs']} / {session['duration_s']:.1f} s; RSS growth: {session['rss_growth_first_to_last_bytes']} bytes",
      f"- Temperature max: {session['temperature_max_millidegree_c']} m°C; thermal throttling: {session['thermal_throttling_observed']} ({session['thermal_throttling_note']})",
      f"- OOM events: {summary['memory_events_delta']}; TARGET_8GB: **{summary['target_8gb_status']}**; performance: **{summary['performance_classification']}**",
      "- Primary bottleneck and next optimization recommendation: classify only after inspecting the completed raw matrix; no optimization was applied in Phase 4E.",""])

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--profile",choices=PROFILE_DIR,default="physical_native");parser.add_argument("--acknowledge-physical-native",action="store_true")
    parser.add_argument("--audit-only",action="store_true");parser.add_argument("--session-queries",type=int,default=50);parser.add_argument("--sustained-minutes",type=int,default=10);parser.add_argument("--include-oracle",action="store_true");args=parser.parse_args()
    audit=physical_audit(ROOT);freeze=verify_freeze();allowed,reason=classify_profile(audit,args.profile,args.acknowledge_physical_native)
    if args.audit_only:
        out=ROOT/"results/phase4e/preparation";out.mkdir(parents=True,exist_ok=True);payload={"audit":audit,"freeze":freeze,"profile_allowed":allowed,"reason":reason,"matrix_executed":False}
        (out/"runner-audit.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n");print(json.dumps({"allowed":allowed,"reason":reason,"environment_type":audit["environment_type"]}));return 0
    if not freeze["ok"]:raise SystemExit(f"FROZEN_ARTIFACT_MISMATCH: {freeze['errors']}")
    if not allowed:raise SystemExit(f"REFUSED_PHYSICAL_LABEL: {reason}")
    result_environment="PHYSICAL_NATIVE" if args.profile=="physical_native" else "PHYSICAL_CONTAINER_LIMITED"
    audit["environment_type"]=result_environment;out=ROOT/"results/phase4e"/PROFILE_DIR[args.profile];out.mkdir(parents=True,exist_ok=True)
    (out/"hardware.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n");(out/"configuration.json").write_text(json.dumps({"profile":args.profile,"freeze":freeze},indent=2,sort_keys=True)+"\n")
    qa=json.loads(QA_PATH.read_text());queries=[q for q in qa["queries"] if q["split"]=="holdout"]
    manifest=json.loads((ROOT/"brain_data/real_knowledge/semantic/manifest.json").read_text());records={r["record_id"]:r for r in manifest["records"]};index=RealKnowledgeIndex.load(INDEX_PATH,manifest["records"])
    events_before=read_key_values(Path("/sys/fs/cgroup/memory.events"));runs=[]
    variants=CANONICAL_VARIANTS+(("oracle",) if args.include_oracle else ())
    for query in queries:
        for variant in variants:
            runs.append(one_run(query,variant,"cold",index,records,True));(out/"raw-runs.json").write_text(json.dumps(runs,indent=2,sort_keys=True)+"\n")
            runs.append(one_run(query,variant,"warm",index,records,False));(out/"raw-runs.json").write_text(json.dumps(runs,indent=2,sort_keys=True)+"\n")
    session=[];started=time.monotonic();turn=0
    while turn<args.session_queries or time.monotonic()-started<args.sustained_minutes*60:
        query=queries[turn%len(queries)];session.append(one_run(query,"brain_ssd","warm",index,records,False));turn+=1
        (out/"session-runs.json").write_text(json.dumps(session,indent=2,sort_keys=True)+"\n")
    canonical=aggregate(runs,variants);events_after=read_key_values(Path("/sys/fs/cgroup/memory.events"));oom_delta=max(0,events_after.get("oom",0)-events_before.get("oom",0));oom_kill_delta=max(0,events_after.get("oom_kill",0)-events_before.get("oom_kill",0))
    brain_warm=canonical.get("brain_ssd:warm",{});all_ok=all(r["qwen"]["return_code"]==0 for r in runs+session)
    system_peak=brain_warm.get("system_ram_used_peak_bytes") or 9*GIB
    if args.profile in ("target_8gb","low_4gb"):
        system_peak=max((r["system"].get("cgroup_memory_current_peak_bytes") or 0 for r in runs+session),default=9*GIB)
    memory_ok=system_peak<=8*GIB
    available_ok=min((r["system"]["mem_available_min_bytes"] or 0 for r in runs+session),default=0)>=128*1024**2
    phase4d=json.loads((ROOT/"results/phase4d/end-to-end.json").read_text());quality_reference=phase4d["summary"]["brain_ssd"]["quality_mean"]
    quality_ok=abs((brain_warm.get("quality_mean") or 0)-quality_reference)<=.125
    required_metrics=("ttft_median_ms","latency_mean_ms","rss_peak_bytes","pss_peak_bytes","system_ram_used_peak_bytes")
    metrics_complete=all(brain_warm.get(key) is not None for key in required_metrics)
    target_pass=all_ok and memory_ok and available_ok and quality_ok and metrics_complete and oom_delta==0 and oom_kill_delta==0
    median_latency=brain_warm.get("ttft_median_ms") or float("inf")
    performance="FAST" if all_ok and median_latency<=5000 else "INTERACTIVE" if all_ok and median_latency<=15000 else "FUNCTIONAL" if all_ok else "FAILED"
    native_is_target=args.profile=="physical_native" and (audit.get("physical_ram_total_bytes") or 99*GIB)<=8*GIB*1.08
    is_target=args.profile=="target_8gb" or native_is_target
    first_penalty={variant:(canonical[f"{variant}:cold"]["ttft_median_ms"]-canonical[f"{variant}:warm"]["ttft_median_ms"]) for variant in variants}
    latencies=[r["pipeline"]["total_ms"] for r in session];rss=[r["qwen"]["metrics"]["rss_bytes_max"] or 0 for r in session]
    midpoint=max(1,len(session)//2)
    session_summary={"runs":len(session),"duration_s":time.monotonic()-started,"rss_peak_bytes":max((r["qwen"]["metrics"]["rss_bytes_max"] or 0 for r in session),default=0),
                     "mem_available_min_bytes":min((r["system"]["mem_available_min_bytes"] or 0 for r in session),default=0),
                     "temperature_max_millidegree_c":max((r["system"]["temperature_max_millidegree_c"] or 0 for r in session),default=0),
                     "rss_growth_first_to_last_bytes":(rss[-1]-rss[0]) if rss else None,
                     "latency_first_half_mean_ms":statistics.mean(latencies[:midpoint]) if latencies else None,
                     "latency_second_half_mean_ms":statistics.mean(latencies[midpoint:]) if len(latencies)>midpoint else None,
                     "thermal_throttling_observed":None,"thermal_throttling_note":"not directly exposed; inspect temperature, frequency and kernel logs"}
    summary={"schema_version":1,"environment_type":result_environment,"profile":args.profile,"native_is_target_8gb":native_is_target,"freeze_id":freeze["freeze_id"],"canonical":canonical,"first_query_penalty_ttft_ms":first_penalty,"session":session_summary,
             "target_8gb_status":("PASS" if target_pass else "FAIL") if is_target else "NOT_APPLICABLE",
             "target_8gb_criteria":{"all_runs_ok":all_ok,"system_ram_within_8gib":memory_ok,"system_responsive_proxy_mem_available_min_128mib":available_ok,"quality_within_one_holdout_case":quality_ok,"phase4d_quality_reference":quality_reference,"metrics_complete":metrics_complete,"no_oom":oom_delta==0 and oom_kill_delta==0},
             "performance_classification":performance,"classification_thresholds_ms":{"fast_ttft_max":5000,"interactive_ttft_max":15000},
             "memory_events_delta":{"oom":oom_delta,"oom_kill":oom_kill_delta},"swap_policy":{"swap_used_peak_bytes":max((r["system"].get("swap_used_peak_bytes") or 0 for r in runs+session),default=0),"architecture_uses_swap":False},"prefetch":False}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    (out/"REPORT.md").write_text(render_report(audit,summary))
    checks={str(p.relative_to(ROOT)):sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!="checksums.json"};(out/"checksums.json").write_text(json.dumps(checks,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
