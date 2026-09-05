#!/usr/bin/env python3
"""Reproducible retrieval-only and CPU-only end-to-end Phase 4D runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.real_knowledge import PAGE_SIZE, sha256_bytes
from brain_ssd.record_retrieval import ContextBuilder, RealKnowledgeIndex, build_prompt, retrieve
from brain_ssd.storage import MMapStorageBackend, touch_view
from brain_ssd.system_metrics import process_io, process_memory
from brain_ssd.telemetry import run_measured

QA_PATH = ROOT / "benchmarks/data/phase4d_real_qa.json"
INDEX_PATH = ROOT / "brain_data/real_knowledge/index/record-index.json.gz"
MODEL_PATH = ROOT / "models/Qwen3-0.6B-Q8_0.gguf"
RUNTIME_PATH = ROOT / "build/llama.cpp/bin/llama-completion"


def percentile(values: list[float], fraction: float) -> float | None:
    if not values: return None
    ordered=sorted(values); return ordered[round((len(ordered)-1)*fraction)]


def extract_from_page(page, record: dict) -> dict:
    start=record["offset"]; payload=bytes(page.data[start:start+record["length"]])
    if sha256_bytes(payload) != record["checksum"]:
        raise ValueError(f"record checksum mismatch: {record['record_id']}")
    result=dict(record); result["text"]=payload.decode("utf-8"); return result


def evaluate_query(index, records_by_id, query, layout: str, mode: str, context_budget: int) -> dict:
    started=time.perf_counter_ns()
    result=retrieve(index,query["query"],records_by_id,mode=mode,max_records=8,max_pages=4,threshold=.20)
    routed=time.perf_counter_ns()
    manifest_path=ROOT/f"brain_data/real_knowledge/{layout}/manifest.json"
    io_before=process_io(); memory_before=process_memory()
    extracted=[]; sink=0; storage_started=time.perf_counter_ns()
    with MMapStorageBackend(manifest_path) as backend:
        for page_id in result.activated_pages:
            page=backend.get_page(page_id,validate="first")
            sink ^= touch_view(page.data)
            for record in result.records:
                if record["page_id"]==page_id: extracted.append(extract_from_page(page,record))
            backend.release_page(page)
        storage_stats=backend.stats()
    storage_finished=time.perf_counter_ns(); io_after=process_io(); memory_after=process_memory()
    context_started=time.perf_counter_ns(); context=ContextBuilder(context_budget).build(extracted); context_finished=time.perf_counter_ns()
    expected=set(query["expected_record_ids"]); got={record["record_id"] for record in result.records}
    pages_expected={records_by_id[rid]["page_id"] for rid in expected}; pages_got=set(result.activated_pages)
    relevant_bytes=sum(records_by_id[rid]["length"] for rid in got & expected)
    return {
        "query_id":query["query_id"], "split":query["split"], "category":query["category"], "query":query["query"],
        "layout":layout, "retrieval_mode":mode, "status":result.status,
        "record_ids":sorted(got), "expected_record_ids":sorted(expected),
        "record_true_positive":len(got&expected), "record_expected":len(expected), "record_retrieved":len(got),
        "page_true_positive":len(pages_got&pages_expected), "page_expected":len(pages_expected), "page_retrieved":len(pages_got),
        "activated_pages":sorted(pages_got), "active_brain_bytes":len(pages_got)*PAGE_SIZE,
        "selected_record_bytes":sum(record["length"] for record in result.records), "relevant_record_bytes":relevant_bytes,
        "knowledge_density":context["bytes"]/max(1,len(pages_got)*PAGE_SIZE),
        "records_per_activated_page":len(got)/max(1,len(pages_got)), "context":context,
        "timing_ms":{"routing":(routed-started)/1e6,"storage":(storage_finished-storage_started)/1e6,
                     "context_build":(context_finished-context_started)/1e6,"retrieval_total":(context_finished-started)/1e6},
        "storage":{"logical_page_bytes":storage_stats["logical_bytes_requested"],
                   "physical_read_bytes":max(0,(io_after.get("read_bytes") or 0)-(io_before.get("read_bytes") or 0)),
                   "minor_faults":None,"major_faults":None,"checksum_errors":storage_stats["checksum_errors"],"sink":sink},
        "process_memory_before":memory_before,"process_memory_after":memory_after,
    }


def aggregate(rows: list[dict]) -> dict:
    tp=sum(row["record_true_positive"] for row in rows); expected=sum(row["record_expected"] for row in rows); retrieved=sum(row["record_retrieved"] for row in rows)
    ptp=sum(row["page_true_positive"] for row in rows); pexpected=sum(row["page_expected"] for row in rows); pretrieved=sum(row["page_retrieved"] for row in rows)
    active=[row["active_brain_bytes"] for row in rows]
    return {"query_count":len(rows),"record_recall":tp/expected if expected else 1.0,"record_precision":tp/retrieved if retrieved else (1.0 if not expected else 0.0),
            "page_recall":ptp/pexpected if pexpected else 1.0,"page_precision":ptp/pretrieved if pretrieved else (1.0 if not pexpected else 0.0),
            "active_brain_mean_bytes":statistics.mean(active),"active_brain_median_bytes":statistics.median(active),
            "knowledge_density_mean":statistics.mean(row["knowledge_density"] for row in rows),
            "context_tokens_mean":statistics.mean(row["context"]["estimated_tokens"] for row in rows),
            "physical_read_bytes_total":sum(row["storage"]["physical_read_bytes"] for row in rows),
            "routing_p50_ms":percentile([row["timing_ms"]["routing"] for row in rows],.5),
            "routing_p95_ms":percentile([row["timing_ms"]["routing"] for row in rows],.95)}


def qwen_command(prompt: str) -> list[str]:
    return [str(RUNTIME_PATH),"--model",str(MODEL_PATH),"--prompt",prompt,"--n-predict","96","--threads","4",
            "--ctx-size","4096","--temp","0","--device","none","--no-display-prompt","--simple-io","--no-warmup",
            "--reasoning","off","--conversation","--single-turn","--perf"]


def clean_answer(stdout: str) -> str:
    text=re.sub(r"<think>.*?</think>","",stdout,flags=re.S).strip()
    return text.removesuffix("> ").strip()


def score_answer(answer: str, query: dict, retrieved: list[str]) -> dict:
    lower=answer.casefold(); groups=query["required_fact_groups"]
    facts=sum(any(term.casefold() in lower for term in alternatives) for alternatives in groups)
    source_ids=set(re.findall(r"\[SOURCE:\s*([0-9a-f]{24})\]",answer,re.I))
    expected=set(query["expected_record_ids"])
    unknown_ok=(not expected and "no_knowledge" in lower)
    return {"required_facts_found":facts,"required_facts_total":len(groups),"required_fact_score":facts/len(groups) if groups else float(unknown_ok),
            "cited_source_ids":sorted(source_ids),"source_correct":bool(source_ids&expected) if expected else unknown_ok,
            "retrieval_supports_expected":bool(set(retrieved)&expected) if expected else not retrieved,
            "groundedness_scope":"required-fact support only; not a general hallucination detector"}


def run_qwen(rows_by_key: dict, queries: list[dict], output: Path) -> list[dict]:
    if not MODEL_PATH.exists() or not RUNTIME_PATH.exists(): raise FileNotFoundError("frozen Qwen model/runtime missing")
    runs=[]
    for query in queries:
        brain=rows_by_key[("semantic","brain",query["query_id"])]
        standard=rows_by_key[("semantic","standard",query["query_id"])]
        manifest=json.loads((ROOT/"brain_data/real_knowledge/semantic/manifest.json").read_text()); by_id={r["record_id"]:r for r in manifest["records"]}
        variants={
            "qwen_only":{"text":"","estimated_tokens":0,"source_ids":[],"bytes":0},
            "standard_retrieval":standard["context"],
            "brain_ssd":brain["context"],
            "oracle":ContextBuilder(2048).build([by_id[rid] for rid in query["expected_record_ids"]]),
        }
        for variant,context in variants.items():
            if variant == "qwen_only":
                prompt=("Answer the technical question from your own internal knowledge. Answer concisely; "
                        "if you do not know, reply exactly NO_KNOWLEDGE.\n\nUSER QUESTION:\n"
                        f"{query['query']}\n\nANSWER:\n/no_think")
            else:
                prompt=build_prompt(query["query"],context)
            measured=run_measured(qwen_command(prompt),sample_interval_s=.02)
            answer=clean_answer(measured["stdout"])
            prompt_match=re.search(r"prompt eval time\s*=.*?([0-9.]+) tokens per second",measured["stderr"],re.I|re.S)
            measured["metrics"]["prompt_tokens_per_second"]=float(prompt_match.group(1)) if prompt_match else None
            measured.pop("samples",None)
            run={"query_id":query["query_id"],"variant":variant,"answer":answer,"context":{k:v for k,v in context.items() if k!="text"},
                 "metrics":measured["metrics"],"return_code":measured["return_code"],"stderr_sha256":hashlib.sha256(measured["stderr"].encode()).hexdigest(),
                 "score":score_answer(answer,query,context["source_ids"])}
            runs.append(run); output.write_text(json.dumps(runs,indent=2,sort_keys=True)+"\n")
    return runs


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--qwen",action="store_true");parser.add_argument("--context-budget-tokens",type=int,default=2048);args=parser.parse_args()
    outdir=ROOT/"results/phase4d";outdir.mkdir(parents=True,exist_ok=True)
    qa=json.loads(QA_PATH.read_text()); rows=[]; rows_by_key={}
    for layout in ("semantic","random"):
        manifest=json.loads((ROOT/f"brain_data/real_knowledge/{layout}/manifest.json").read_text());by_id={r["record_id"]:r for r in manifest["records"]}
        index=RealKnowledgeIndex.load(INDEX_PATH,manifest["records"])
        for mode in ("standard","brain"):
            for query in qa["queries"]:
                row=evaluate_query(index,by_id,query,layout,mode,args.context_budget_tokens);rows.append(row);rows_by_key[(layout,mode,query["query_id"])]=row
    retrieval={"schema_version":1,"configuration":{"logical_page_bytes":PAGE_SIZE,"storage_extent_bytes":4*PAGE_SIZE,"storage_access":"logical-only","residency":"KernelOnly","prefetch":False,"context_budget_tokens":args.context_budget_tokens},
               "rows":rows,"aggregates":{f"{layout}:{mode}:{split}":aggregate([r for r in rows if r["layout"]==layout and r["retrieval_mode"]==mode and r["split"]==split]) for layout in ("semantic","random") for mode in ("standard","brain") for split in ("development","holdout")}}
    (outdir/"retrieval-only.json").write_text(json.dumps(retrieval,indent=2,sort_keys=True)+"\n")
    if args.qwen:
        holdout=[query for query in qa["queries"] if query["split"]=="holdout"]
        runs=run_qwen(rows_by_key,holdout,outdir/"end-to-end-partial.json")
        summary={variant:{"queries":len(selected:= [r for r in runs if r["variant"]==variant]),
                          "quality_mean":statistics.mean(r["score"]["required_fact_score"] for r in selected),
                          "ttft_median_ms":statistics.median(r["metrics"]["ttft_ms"] for r in selected if r["metrics"]["ttft_ms"] is not None),
                          "generation_tokens_per_second_mean":statistics.mean(r["metrics"]["tokens_per_second"] for r in selected if r["metrics"]["tokens_per_second"] is not None),
                          "latency_mean_ms":statistics.mean(r["metrics"]["latency_ms"] for r in selected),
                          "rss_max_bytes":max(r["metrics"]["rss_bytes_max"] or 0 for r in selected),
                          "pss_max_bytes":max(r["metrics"]["pss_bytes_max"] or 0 for r in selected),
                          "anonymous_max_bytes":max(r["metrics"]["anonymous_bytes_max"] or 0 for r in selected),
                          "file_backed_max_bytes":max(r["metrics"]["rss_file_bytes_max"] or 0 for r in selected)} for variant in ("qwen_only","standard_retrieval","brain_ssd","oracle")}
        (outdir/"end-to-end.json").write_text(json.dumps({"schema_version":1,"runs":runs,"summary":summary},indent=2,sort_keys=True)+"\n")
    print(json.dumps(retrieval["aggregates"],sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
