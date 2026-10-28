"""Brain-SSD experimental adapter for original Luna Forge Zero models.

Runs ONE model per request, maps PyTorch checkpoints from SSD, and retrieves
checksummed knowledge pages with the existing Brain-SSD storage contract.
Does not modify frozen experiments, Qwen, Luna chat or training weights.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from time import perf_counter
import unicodedata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
PAGE_SIZE = 4096
STOP = {"jogo","jogos","para","com","uma","crie","desenvolva","quero","como","faca","onde","the","and","game","luna","sistema"}


def _terms(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return set(re.findall(r"[a-z0-9_]{3,}", value)) - STOP


def _sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def _rss():
    try:
        import psutil
        return psutil.Process().memory_info().rss
    except ImportError:
        return None


def select_model(query, mode="auto"):
    if mode != "auto":
        if mode not in {"plan", "code"}:
            raise ValueError("Invalid mode")
        return mode
    if _terms(query).intersection({"codigo","codifique","implemente","gdscript","javascript","script","function","func","bug","corrija"}):
        return "code"
    return "plan"


def build_knowledge(folder, records):
    """Generate independent 4 KiB Brain-SSD pages; not a frozen research corpus."""
    folder = Path(folder)
    if not records:
        raise ValueError("At least one reviewed record required")
    folder.mkdir(parents=True, exist_ok=True)
    pages, catalog = [], []
    with (folder / "brain.dat").open("wb") as stream:
        for index, record in enumerate(records):
            title = str(record["title"])
            payload = (title + "\n" + str(record["text"])).encode("utf-8")
            if len(payload) > PAGE_SIZE or not payload:
                raise ValueError("Skill must fit within 4 KiB")
            page = payload + b"\0" * (PAGE_SIZE - len(payload))
            stream.write(page)
            pages.append({"page_id":index,"version":1,"offset":index*PAGE_SIZE,"size":PAGE_SIZE,
                          "checksum":hashlib.sha256(page).hexdigest(),"related_pages":[]})
            catalog.append({"page_id":index,"title":title,"length":len(payload),
                            "terms":sorted(_terms(payload.decode("utf-8")))})
    manifest = {"schema_version":1,"data_file":"brain.dat","corpus_size_bytes":len(pages)*PAGE_SIZE,
                "page_size_bytes":PAGE_SIZE,"page_count":len(pages),"pages":pages,"records":catalog}
    (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"pages":len(pages),"logical_storage_bytes":len(pages)*PAGE_SIZE}


@contextmanager
def skill_pages(folder, query, limit=2):
    manifest_path = Path(folder)/"manifest.json"
    if not manifest_path.is_file() or limit <= 0:
        yield {"skills":[],"page_reads":0,"logical_bytes":0,"storage":"none"}
        return
    from brain_ssd.storage import MMapStorageBackend
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    terms = _terms(query)
    ranked = sorted(
        ((len(terms.intersection(set(row["terms"]))),row) for row in manifest["records"]),
        key=lambda x:(-x[0],x[1]["page_id"]))
    selected = [record for score,record in ranked if score>0][:min(limit,2)]
    skills=[]
    with MMapStorageBackend(manifest_path) as backend:
        for record in selected:
            page = backend.get_page(record["page_id"],validate="first")
            try:
                skills.append({"title":record["title"],"page_id":record["page_id"],
                               "text":bytes(page.data[:record["length"]]).decode("utf-8")})
            finally:
                backend.release_page(page)
        yield {"skills":skills,"page_reads":len(skills),
               "logical_bytes":backend.stats()["logical_bytes_requested"],
               "storage":"brain_ssd.storage.MMapStorageBackend"}


def _load(folder, max_mib):
    import torch
    checkpoint = folder/"weights.pt"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Missing local weights: {checkpoint}")
    if checkpoint.stat().st_size > max_mib*1024*1024:
        raise MemoryError("Checkpoint exceeds file-size guard (not a RAM hard cap)")
    report = json.loads((folder/"report.json").read_text(encoding="utf-8"))
    expected = report.get("weights_sha256",report.get("sha256"))
    if expected and expected != _sha(checkpoint):
        raise ValueError("SHA-256 checkpoint integrity failure")
    return torch.load(checkpoint,map_location="cpu",weights_only=True,mmap=True),report


def infer(request, checkpoints, knowledge=None, mode="auto", max_mib=64, max_chars=160, seed=4):
    """Load only the selected model; no generated code is executed."""
    import torch
    torch.set_num_threads(min(torch.get_num_threads(),4))
    choice = select_model(request,mode)
    identity = "luna-forge-zero-v0" if choice=="plan" else "luna-minicoder-zero-v0"
    folder = Path(checkpoints)/identity
    started = perf_counter()
    before = _rss()
    with skill_pages(knowledge or HERE/"knowledge_pages",request) as context:
        state,report = _load(folder,max_mib)
        if choice=="plan":
            from luna_model import LunaGamePlanner,predict
            vocab=json.loads((folder/"vocab.json").read_text(encoding="utf-8"))
            cfg=json.loads((folder/"config.json").read_text(encoding="utf-8"))
            model=LunaGamePlanner(len(vocab),cfg["dim"],cfg["hidden"])
            model.load_state_dict(state,assign=True)
            model.eval()
            result=predict(request,model,vocab)
        else:
            from luna_codegen_model import Config,LunaMiniCoder
            model=LunaMiniCoder(Config(**report["config"]))
            model.load_state_dict(state,assign=True)
            model.eval()
            torch.manual_seed(seed)
            result={"raw_generated_text":model.generate(request,chars=min(512,max(1,max_chars)),temperature=.6),
                    "warning":"Experimental output, not syntax/behavior-verified and never executed here"}
        weights=sum(p.numel()*p.element_size() for p in model.parameters())
        del model,state
    gc.collect()
    return {"model":identity,"route":choice,"inference":result,
            "retrieved_skills":context["skills"],"telemetry":{
                "weight_loading":"torch.load(mmap=True,weights_only=True) + assign=True",
                "knowledge_backend":context["storage"],
                "active_model_weight_bytes_logical":weights,
                "activated_knowledge_pages":context["page_reads"],
                "knowledge_bytes_logical":context["logical_bytes"],
                "process_rss_before":before,"process_rss_after":_rss(),
                "elapsed_seconds":round(perf_counter()-started,4),
                "warning":"SSD does not replace RAM; budget is checkpoint-file size only, not physical memory"}}


def add_feedback(db, model, task, result):
    """Journal is not training: every example stays pending human review."""
    db=Path(db)
    db.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY, utc TEXT NOT NULL, model TEXT NOT NULL, task TEXT NOT NULL, output TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0)")
        row=conn.execute("INSERT INTO feedback(utc,model,task,output,approved) VALUES (?,?,?,?,0)",
                         (datetime.now(timezone.utc).isoformat(),model,task,result[:40000]))
        return row.lastrowid


def main():
    p=argparse.ArgumentParser(description="Experimental Luna Forge Zero Brain-SSD bridge")
    p.add_argument("action",choices=("status","build-knowledge","plan","code","auto","feedback"))
    p.add_argument("--request",default="Crie um jogo de plataforma com pulo")
    p.add_argument("--checkpoints",type=Path,default=HERE/"checkpoints")
    p.add_argument("--skills",type=Path,default=HERE/"knowledge_pages")
    p.add_argument("--skills-source",type=Path,default=HERE/"skills.json")
    p.add_argument("--db",type=Path,default=HERE/"state"/"feedback.sqlite3")
    p.add_argument("--model-name",default="luna-forge-zero-v0")
    p.add_argument("--output",default="")
    p.add_argument("--max-mib",type=int,default=64)
    p.add_argument("--max-chars",type=int,default=160)
    a=p.parse_args()
    if a.action=="status":
        result={"experimental":True,"weights_present":{name:(a.checkpoints/name/"weights.pt").is_file()
                for name in ("luna-forge-zero-v0","luna-minicoder-zero-v0")},
                "brain_ssd_repository_backend":(SRC/"brain_ssd"/"storage.py").is_file(),
                "model_promotion":False}
    elif a.action=="build-knowledge":
        result=build_knowledge(a.skills,json.loads(a.skills_source.read_text(encoding="utf-8")))
    elif a.action=="feedback":
        result={"feedback_id":add_feedback(a.db,a.model_name,a.request,a.output),"status":"pending_review"}
    else:
        result=infer(a.request,a.checkpoints,a.skills,mode=a.action,max_mib=a.max_mib,max_chars=a.max_chars)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
