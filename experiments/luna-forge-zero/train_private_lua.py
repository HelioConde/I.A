"""Local-only incremental experimental MiniCoder training on user-authorized Lua.

Reads ONLY regular .lua files on the user's machine after explicit rights
acknowledgment. No extraction, executable execution, network or data upload.
The model can memorize training data: never publish private checkpoints.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import re
import stat

HERE=Path(__file__).resolve().parent
OUTPUT_ROOT=HERE/"private_lua_training"
PARENT_MODELS=HERE/"external_data"
MAX_READ=65536
MAX_BUDGET_MIB=96
BLOCK=128
SKIP_PATH_PARTS=frozenset((
    "elsword","database","databases","backup","backups","billing",
    "account","accounts","users","user","credentials","secrets",
    "authentication","auth","private",".git","hshield",
))
PRIVATE_PATTERNS=(
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----",re.I),
    re.compile(rb"\b(?:password|passwd|private[_-]?key|api[_-]?key|access[_-]?token|secret[_-]?key)\b",re.I),
    re.compile(rb"\b(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})\b"),
    re.compile(rb"\b(?:jdbc:|mongodb://|postgres://|mysql://|sqlserver://)",re.I),
)

def no_links(path: Path) -> bool:
    try:
        info=os.lstat(path)
        return not (stat.S_ISLNK(info.st_mode) or
                    bool(getattr(info,"st_file_attributes",0)&1024))
    except OSError:
        return False

def check_root(folder: Path) -> Path:
    source=Path(folder).expanduser()
    if not source.is_dir() or not no_links(source):
        raise ValueError("Pasta inexistente ou junction/symlink nao permitido")
    resolved=source.resolve()
    if resolved==HERE.resolve() or HERE.resolve() in resolved.parents:
        raise ValueError("Dados de treinamento precisam estar fora do repositorio")
    return resolved

def list_safe_lua(folder: Path) -> tuple[list[Path],int,int]:
    """Only gather in-process paths; never serialize path or filenames."""
    root=check_root(folder)
    paths=[]
    seen=0
    skipped_links=0
    def onerror(error):
        raise OSError("Nao foi possivel ler uma subpasta") from error
    for current,dirs,names in os.walk(root,topdown=True,followlinks=False,onerror=onerror):
        allowed=[]
        for name in dirs:
            item=Path(current)/name
            if not no_links(item):
                skipped_links+=1
            elif name.lower() not in SKIP_PATH_PARTS:
                allowed.append(name)
        dirs[:]=allowed
        for name in names:
            if not name.lower().endswith(".lua"):
                continue
            seen+=1
            candidate=Path(current)/name
            if not no_links(candidate):
                skipped_links+=1
                continue
            if any(p.lower() in SKIP_PATH_PARTS for p in candidate.relative_to(root).parts[:-1]):
                continue
            # Exclude file names implying sensitive content; other names
            # are only used in RAM, never printed or persisted.
            if any(token in name.lower() for token in ("password","secret","account","billing","login","credential","auth","token")):
                continue
            try:
                info=os.stat(candidate,follow_symlinks=False)
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_size<256:
                continue
            paths.append(candidate)
    return paths,seen,skipped_links

def safe_sample(path: Path, limit: int=MAX_READ) -> tuple[bytes|None,str]:
    """Read at most 64 KiB; do not extract, execute, decompile or log source."""
    if not no_links(path):
        return None,"link"
    with path.open("rb") as stream:
        raw=stream.read(limit)
    if raw.startswith((b"\x1bLua",b"\x1bLJ",b"\x1bKL")):
        return None,"bytecode"
    if b"\x00" in raw or not raw.strip():
        return None,"binary_or_blank"
    try:
        text=raw.decode("utf-8")
    except UnicodeDecodeError:
        return None,"not_utf8"
    if any(pattern.search(raw) for pattern in PRIVATE_PATTERNS):
        return None,"potential_secret"
    # ASCII-only tokenization is an architectural limitation of MiniCoder,
    # not a property of the original file. Content remains in RAM only.
    clean=text.encode("ascii",errors="replace")
    if len(clean)<=BLOCK+1:
        return None,"too_short"
    return clean,"eligible"

def prepare(folder: Path, *, seed: int=20261028,
            max_mib: int=64, limit_per_file: int=MAX_READ) -> tuple[dict,list,list]:
    """Sample a capped subset; ensure holdout files never enter training."""
    if not 1<=max_mib<=MAX_BUDGET_MIB:
        raise ValueError("max_mib must be 1..96")
    if not 1024<=limit_per_file<=MAX_READ:
        raise ValueError("per-file sample must be 1024..65536 bytes")
    root=check_root(folder)
    paths,seen,skipped_links=list_safe_lua(root)
    random.Random(seed).shuffle(paths)
    allowed=max_mib*1024*1024
    budget=0
    train=[]
    holdout=[]
    skipped=Counter()
    for path in paths:
        if budget>=allowed:
            break
        try:
            payload,reason=safe_sample(path,limit=min(limit_per_file,allowed-budget))
        except OSError:
            skipped["read_error"]+=1
            continue
        if payload is None:
            skipped[reason]+=1
            continue
        # Stable per-file split without logging filenames or content hashes.
        # Holdout never participates in gradient updates.
        rel=path.relative_to(root).as_posix().encode("utf-8")
        is_holdout=int.from_bytes(hashlib.sha256(rel).digest()[:4],"big")%10==0
        (holdout if is_holdout else train).append(payload)
        budget+=len(payload)
    if len(train)<8 or len(holdout)<2:
        raise ValueError("Poucos arquivos Lua elegiveis para treino/holdout isolados")
    summary={
        "schema":"luna-private-lua-training-v1",
        "source_location":"user-local-only; filenames and paths never saved",
        "source_lua_files_discovered":seen,
        "sampled_files":len(train)+len(holdout),
        "train_files":len(train),"heldout_files":len(holdout),
        "sampled_source_bytes":budget,
        "max_read_per_file_bytes":limit_per_file,
        "max_dataset_mib":max_mib,
        "skipped_by_reason":dict(sorted(skipped.items())),
        "skipped_links":skipped_links,
        "source_files_exported":0,"commercial_assets_used":0,
        "backups_and_archives_opened":0,"network_requests":0,
        "disclaimer":"Experimental byte/character modeling; no proof of code or game ability. Weights may memorize protected source and must stay private."
    }
    return summary,train,holdout

def parent_checkpoint():
    """Use only an existing verified private local-candidate in external_data."""
    from preview_local_candidate import candidates,verify_candidate
    options=candidates(PARENT_MODELS)
    if not options:
        raise FileNotFoundError("Nao ha checkpoint MiniCoder local verificado. Treine primeiro a opcao 4.")
    source=options[0]
    report,weights=verify_candidate(source,PARENT_MODELS)
    return report,weights

def private_models() -> list[Path]:
    if not OUTPUT_ROOT.is_dir():
        return []
    return sorted((p for p in OUTPUT_ROOT.iterdir() if p.is_dir()
                   and p.name.startswith("private-lua-")
                   and (p/"report.json").is_file() and (p/"weights.pt").is_file()),
                  key=lambda p:p.name,reverse=True)

def train(folder:Path, *, max_mib:int=64, steps:int=300,
          batch:int=12, threads:int=4, seed:int=20261028) -> dict:
    if not 1<=steps<=1500 or not 1<=batch<=24 or not 1<=threads<=8:
        raise ValueError("Outside safe CPU training budgets")
    # Validate input and parent before touching any source contents.
    check_root(folder)
    base_report,base_weights=parent_checkpoint()
    summary,training,heldout=prepare(folder,seed=seed,max_mib=max_mib)
    import torch
    from luna_codegen_model import Config,LunaMiniCoder
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    cfg=Config(**base_report["config"])
    if cfg.vocab!=128 or cfg.block!=BLOCK:
        raise ValueError("Unsupported MiniCoder tokenizer/context")
    model=LunaMiniCoder(cfg)
    model.load_state_dict(torch.load(base_weights,weights_only=True,map_location="cpu",mmap=True),assign=True)
    optim=torch.optim.AdamW(model.parameters(),lr=0.00025,weight_decay=.01)
    rng=random.Random(seed+17)
    # Reuse exactly the same unseen-file windows for before and after scores.
    def get_batch(items, n, randomizer):
        xs=[];ys=[]
        for _ in range(n):
            sample=randomizer.choice(items)
            start=randomizer.randrange(0,len(sample)-BLOCK)
            chunk=sample[start:start+BLOCK+1]
            token=torch.tensor(list(chunk),dtype=torch.long)
            xs.append(token[:-1]);ys.append(token[1:])
        return torch.stack(xs),torch.stack(ys)
    @torch.no_grad()
    def evaluate():
        model.eval()
        randomizer=random.Random(seed+999)
        losses=[]
        for _ in range(5):
            x,y=get_batch(heldout,batch,randomizer)
            _,loss=model(x,y)
            losses.append(loss.item())
        return round(sum(losses)/len(losses),6)
    before=evaluate()
    history=[]
    for step in range(1,steps+1):
        model.train()
        x,y=get_batch(training,batch,rng)
        _,loss=model(x,y)
        optim.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        optim.step()
        if step in (1,steps) or step%50==0:
            record={"step":step,"train_loss":round(loss.detach().item(),5)}
            history.append(record)
            print(json.dumps(record),flush=True)
    after=evaluate()
    # Private and ignored by Git. Never make a public artifact.
    dest=OUTPUT_ROOT/("private-lua-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    if dest.exists():
        raise FileExistsError("Refusing to replace an existing private checkpoint")
    OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
    dest.mkdir(mode=0o700)
    torch.save(model.state_dict(),dest/"weights.pt")
    digest=hashlib.sha256((dest/"weights.pt").read_bytes()).hexdigest()
    report={
        **summary,
        "status":"private_experimental_checkpoint_not_promoted",
        "training":"Incremental MiniCoder training with local Lua files supplied by user; no Qwen weights involved",
        "architecture":base_report["config"],
        "parent_weights_sha256":base_report["weights_sha256"],
        "weights_sha256":digest,
        "steps":steps,"batch":batch,"seed":seed,
        "heldout_lua_loss_before":before,"heldout_lua_loss_after":after,
        "history":history,
        "model_promotion_allowed":False,
        "source_exported":False,
        "code_executed":False,
        "isolated_model_folder":True,
    }
    (dest/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"trained_private_locally",
                      "saved_only_to_private_folder":True,"sampled_files":summary["sampled_files"],
                      "train_files":summary["train_files"],"holdout_files":summary["heldout_files"],
                      "loss_before":before,"loss_after":after,
                      "checkpoint_folder":str(dest),
                      "not_a_game_creation_success":True},ensure_ascii=False,indent=2))
    return report

def main():
    p=argparse.ArgumentParser(description="Experimental, rights-gated local-only Lua training")
    p.add_argument("action",choices=("dry-run","train","list"))
    p.add_argument("--source",type=Path,default=Path.home()/"Documents"/"grand chase files")
    p.add_argument("--acknowledge-rights",action="store_true",
                   help="I have reviewed rights/permission for local model-training of these scripts.")
    p.add_argument("--max-mib",type=int,default=64)
    p.add_argument("--steps",type=int,default=300)
    p.add_argument("--batch",type=int,default=12)
    p.add_argument("--threads",type=int,default=4)
    args=p.parse_args()
    if args.action=="list":
        print(json.dumps({"private_candidates":len(private_models()),"model_promoted":False,
                          "cloud_uploads":0},indent=2))
        return
    if not args.acknowledge_rights:
        raise SystemExit("Training source rights not confirmed. Inspect permission and pass --acknowledge-rights.")
    if args.action=="dry-run":
        summary,_,_=prepare(args.source,max_mib=args.max_mib)
        print(json.dumps({**summary,"weights_modified":False,"source_files_executed":0},
                         ensure_ascii=False,indent=2))
        return
    train(args.source,max_mib=args.max_mib,steps=args.steps,batch=args.batch,threads=args.threads)

if __name__=="__main__":
    main()
