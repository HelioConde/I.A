"""Auditable, pinned, code-only GitHub corpus for Luna GameCoder research.

Only explicitly approved MIT-licensed repositories. NO execution of retrieved code.
Usage: python github_corpus.py collect --out external_data
       python github_corpus.py verify --out external_data
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

MAX_FILE = 100_000
MAX_TOTAL = 1_500_000
RAW_HOST = "https://raw.githubusercontent.com/"
SCHEMA = "luna-github-v1"

SOURCES = (
    dict(repo="godotengine/godot-demo-projects",
         commit="b761b4cd5718a7118f2c95eb55f181d0a5f004f1",
         evidence="LICENSE.md", evidence_phrase="MIT", license="MIT",
         split="train", category="godot4",
         files=("2d/kinematic_character/player/player.gd",
                "2d/platformer/player/player.gd",
                "2d/platformer/enemy/enemy.gd",
                "2d/platformer/game.gd",
                "2d/dodge_the_creeps/player.gd",
                "2d/dodge_the_creeps/mob.gd",
                "2d/physics_platformer/player/player.gd")),
    dict(repo="statico/godot-roguelike-example",
         commit="5fa12fd3206df9ce42284cf7aab6b41b69b7fca6",
         evidence="LICENSE", evidence_phrase="MIT", license="MIT",
         split="train", category="godot4",
         files=("src/combat.gd", "src/monster_ai.gd", "src/pathfinding.gd",
                "src/damage.gd", "src/item.gd", "src/dice.gd", "src/map.gd")),
    dict(repo="phaserjs/examples",
         commit="eb87db8355861ae222d0c5cd13aae54c2d7d72ae",
         evidence="README.md",
         evidence_phrase="source code in this repo is released under the MIT license",
         license="MIT", split="train", category="phaser",
         files=("public/src/physics/arcade/basic platform.js",
                "public/src/physics/arcade/gravity.js",
                "public/src/physics/arcade/collision direction.js",
                "public/src/physics/arcade/bullets group.js",
                "public/src/input/keyboard/cursor keys.js")),
    dict(repo="stm1978/retro-platformer",
         commit="9835295888c7cb8afa795ca2a31707a65167c2ea",
         evidence="LICENSE", evidence_phrase="MIT", license="MIT",
         split="holdout", category="canvas",
         files=("src/player.js", "src/enemy.js", "src/game.js",
                "src/camera.js", "src/input.js", "src/level.js")),
)

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def raw_url(repo: str, commit: str, path: str) -> str:
    assert re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo)
    assert re.fullmatch(r"[a-f0-9]{40}", commit)
    assert re.fullmatch(r"[a-zA-Z0-9 _./-]+", path) and ".." not in path.split("/")
    return RAW_HOST + repo + "/" + commit + "/" + path.replace(" ", "%20")

def retrieve(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent":"Luna-Forge-Corpus/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError("unexpected status")
        data = response.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ValueError("File or license exceeds per-file cap")
        return data

def collect(out: Path, fetch=retrieve) -> dict:
    out = Path(out)
    rows, notices, cumulative = [], [], 0
    for source in SOURCES:
        license_bytes = fetch(raw_url(source["repo"], source["commit"], source["evidence"]))
        license_text = license_bytes.decode("utf-8").casefold()
        if source["evidence_phrase"].casefold() not in license_text:
            raise ValueError("License evidence missing for " + source["repo"])
        notices.append({"repo":source["repo"], "commit":source["commit"],
                        "license":source["license"], "license_source":source["evidence"],
                        "license_sha256":sha256(license_bytes),
                        "license_text":license_bytes.decode("utf-8")})
        for path in source["files"]:
            if not path.endswith((".gd", ".js", ".ts", ".tsx")):
                raise ValueError("Non-code path prohibited")
            payload = fetch(raw_url(source["repo"], source["commit"], path))
            if b"\x00" in payload:
                raise ValueError("Binary file rejected")
            text = payload.decode("utf-8").replace("\r\n", "\n")
            cumulative += len(payload)
            if cumulative > MAX_TOTAL:
                raise ValueError("Corpus exceeds size cap")
            rows.append({"id":sha256((source["repo"] + "\0" + source["commit"] + "\0" + path).encode())[:24],
                         "repository":source["repo"], "commit":source["commit"],
                         "path":path, "license":source["license"], "split":source["split"],
                         "category":source["category"],
                         "sha256":sha256(payload),
                         "normalized_sha256":sha256(text.encode("utf-8")),
                         "source_url":raw_url(source["repo"], source["commit"], path),
                         "code":text})
    if not rows or not any(r["split"]=="holdout" for r in rows):
        raise ValueError("Both split groups required")
    if {r["repository"] for r in rows if r["split"]=="train"} & {r["repository"] for r in rows if r["split"]=="holdout"}:
        raise ValueError("Repository leakage between train and holdout")
    out.mkdir(parents=True, exist_ok=True)
    corpus = out / "corpus.jsonl"
    corpus.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (out / "LICENSE_NOTICES.json").write_text(json.dumps(notices, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = {"schema":SCHEMA,"source_repositories":len(SOURCES),
             "train_repositories":sorted({r["repository"] for r in rows if r["split"]=="train"}),
             "holdout_repositories":sorted({r["repository"] for r in rows if r["split"]=="holdout"}),
             "files":len(rows),"train_files":sum(r["split"]=="train" for r in rows),
             "holdout_files":sum(r["split"]=="holdout" for r in rows),
             "code_bytes":cumulative,"corpus_sha256":sha256(corpus.read_bytes()),
             "licenses_sha256":sha256((out/"LICENSE_NOTICES.json").read_bytes()),
             "note":"MIT source code only; third-party graphics/audio excluded; no code executed"}
    (out / "manifest.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return stats

def verify(out: Path) -> dict:
    out=Path(out)
    manifest=json.loads((out/"manifest.json").read_text(encoding="utf-8"))
    corpus_bytes = (out/"corpus.jsonl").read_bytes()
    if sha256(corpus_bytes) != manifest["corpus_sha256"]:
        raise ValueError("Dataset checksum mismatch")
    notices_path = out / "LICENSE_NOTICES.json"
    notices_bytes = notices_path.read_bytes()
    if sha256(notices_bytes) != manifest["licenses_sha256"]:
        raise ValueError("License notice checksum mismatch")
    notices = json.loads(notices_bytes)
    sources = {s["repo"]:s for s in SOURCES}
    rows = [json.loads(line) for line in corpus_bytes.decode("utf-8").splitlines()]
    expected = {(s["repo"], p) for s in SOURCES for p in s["files"]}
    if {(r["repository"],r["path"]) for r in rows} != expected or len(rows) != len(expected):
        raise ValueError("Dataset file list mismatch")
    notice_by_repo = {notice["repo"]: notice for notice in notices}
    if len(notice_by_repo) != len(SOURCES) or set(notice_by_repo) != set(sources):
        raise ValueError("License notice repository list mismatch")
    for repo, source in sources.items():
        notice = notice_by_repo[repo]
        if (
            notice.get("commit") != source["commit"]
            or notice.get("license") != source["license"]
            or notice.get("license_source") != source["evidence"]
            or source["evidence_phrase"].casefold()
            not in notice.get("license_text", "").casefold()
        ):
            raise ValueError("License evidence mismatch for " + repo)
    for row in rows:
        spec=sources[row["repository"]]
        if (
            row["commit"] != spec["commit"]
            or row["split"] != spec["split"]
            or row["license"] != spec["license"]
            or row["category"] != spec["category"]
            or row["source_url"] != raw_url(row["repository"], row["commit"], row["path"])
        ):
            raise ValueError("Source provenance mismatch")
        if not row["code"].strip() or "\0" in row["code"]:
            raise ValueError("Invalid source code")
        if "normalized_sha256" in row and sha256(row["code"].encode("utf-8")) != row["normalized_sha256"]:
            raise ValueError("Normalized source checksum mismatch")
        if not re.fullmatch(r"[a-f0-9]{64}", row["sha256"]):
            raise ValueError("Invalid source checksum")
    train_files = sum(r["split"] == "train" for r in rows)
    holdout_files = sum(r["split"] == "holdout" for r in rows)
    train_repos = sorted({r["repository"] for r in rows if r["split"] == "train"})
    holdout_repos = sorted({r["repository"] for r in rows if r["split"] == "holdout"})
    if (
        manifest["train_files"] != train_files
        or manifest["holdout_files"] != holdout_files
        or manifest["train_repositories"] != train_repos
        or manifest["holdout_repositories"] != holdout_repos
        or set(train_repos) & set(holdout_repos)
    ):
        raise ValueError("Split manifest mismatch")
    return {"verified":True,"files":len(rows),"repos":len(sources),
            "train":train_files,"holdout":holdout_files}

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("action", choices=["collect","verify"])
    cli.add_argument("--out",type=Path,default=Path("external_data"))
    args=cli.parse_args()
    print(json.dumps(collect(args.out) if args.action=="collect" else verify(args.out), indent=2, ensure_ascii=False))

if __name__=="__main__":
    main()
