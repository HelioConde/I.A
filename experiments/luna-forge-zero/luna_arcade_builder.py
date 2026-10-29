"""Local Ollama gameplay builder. Generated code is NEVER executed on the host.

The playable engine and reference gameplay are manually authored. Only the
updateGame function comes from an explicitly invoked pretrained Ollama model.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4

from luna_coder_ollama import (
    DEFAULT_MODEL, MODELS, LocalModelError, chat, extract_code,
    installed_models, syntax_check,
)

HERE = Path(__file__).resolve().parent
DEMO = HERE / "luna-arcade-sandbox"
RUNS = HERE / "reports" / "luna_arcade_runs"
ASSETS = ("index.html", "play.html", "style.css", "engine.js")
MAX_TASK = 900
MAX_JS = 16_384

SYSTEM = (
    "You write code for an ORIGINAL small JavaScript canvas platform game. "
    "Return ONLY one complete global JavaScript ES2020 function, named "
    "updateGame(state,input,dt). No imports, external code, globals, browser, "
    "network, storage, events, rendering, timers or API calls. Use ordinary "
    "JavaScript expressions, arrays, objects and Math. Change the given state "
    "in place and return it. Close every brace. No explanatory text."
)
TASK_CONTRACT = (
    "Implement gameplay for a 960x540 original 2D platformer. "
    "A human-authored engine already renders state, handles keyboard/touch controls "
    "and calls the function 60 times per second. Author ONLY gameplay logic.\n"
    "The exact signature is function updateGame(state,input,dt) {...}\n"
    "state.status: 'playing'|'won'|'lost'; state.width=960, state.floor=464, "
    "state.exitX=895. state.player: {x,y,w,h,vx,vy,hp,hurtTime,grounded}. "
    "state.platforms: rectangles {x,y,w,h} with one-way tops. "
    "state.enemies: {x,y,w,h,left,right,direction,speed}. "
    "state.stars: {x,y,taken}, collected near player center. "
    "input.left/right/jump are booleans, dt is elapsed seconds.\n"
    "Requirements: horizontal speed ~265px/s; jump only when grounded; gravity "
    "~1550px/s^2; land on floor and platform tops; clamp x to world; enemy "
    "patrol and contact damage with temporary invulnerability; collect stars; "
    "when all stars are collected and player reaches exitX, status='won'; "
    "when hp<=0, status='lost'. Return state.\n"
    "No classes, extra global functions, imports or browser APIs; local arrow "
    "helpers inside updateGame are allowed."
)
# Defense in depth only, not a guarantee that arbitrary JS is safe.
FORBIDDEN = re.compile(
    r"\b(?:fetch|require|import|eval|Function|XMLHttpRequest|WebSocket|"
    r"Worker|SharedWorker|document|window|navigator|location|localStorage|"
    r"sessionStorage|globalThis|process|setTimeout|setInterval|alert|"
    r"prompt|confirm|postMessage)\b|__proto__|\bprototype\b|\bconstructor\b",
    re.IGNORECASE,
)


def validate_candidate(source: str) -> tuple[bool, str]:
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_JS:
        return False, "Source exceeds 16 KiB"
    if not re.match(r'^\s*(?:"use strict";\s*)?function\s+updateGame\s*\(', source):
        return False, "Expected one global function updateGame"
    if len(re.findall(r"\bfunction\s+updateGame\s*\(", source)) != 1:
        return False, "Duplicate updateGame definitions"
    if FORBIDDEN.search(source):
        return False, "Forbidden browser/network/dynamic-execution identifier"
    if re.search(r"\bwhile\s*\(|\bfor\s*\(\s*;\s*;\s*\)", source):
        return False, "Unbounded loops require manual redesign"
    return True, "passed conservative source filter"


def build(task: str, model: str = DEFAULT_MODEL, *, root: Path | None = None,
          request=chat) -> dict:
    task = task.strip()
    if not 1 <= len(task) <= MAX_TASK:
        raise ValueError("Task must contain 1..900 characters")
    if model not in MODELS:
        raise ValueError("Unapproved local model")
    root = Path(root) if root is not None else RUNS
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": TASK_CONTRACT + "\nOptional flavor preference:\n" + task},
    ]
    code = ""
    failure = ""
    attempts = 0
    for attempt in range(2):
        attempts += 1
        code = extract_code(request(model, messages)).strip()
        allowed, reason = validate_candidate(code)
        parsed = syntax_check(code) if allowed else {"status": "fail", "reason": reason}
        if allowed and parsed["status"] == "pass":
            break
        failure = parsed.get("reason", "Syntax checker unavailable")
        if attempt == 0:
            messages.extend([
                {"role": "assistant", "content": code[:MAX_JS]},
                {"role": "user", "content": (
                    "Return one COMPLETE corrected updateGame function and nothing "
                    "else. Previous candidate was rejected: " + failure[:550] +
                    ". Follow the exact state contract and close every bracket."
                )},
            ])
    else:
        return {
            "status": "rejected_no_preview", "attempts": attempts,
            "model": model, "reason": failure[:600],
            "code_executed": False, "output_written": False,
        }

    folder = root / (
        "run-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") +
        "-" + uuid4().hex[:8]
    )
    folder.mkdir(parents=True, exist_ok=False)
    for filename in ASSETS:
        shutil.copyfile(DEMO / filename, folder / filename)
    (folder / "gameplay.js").write_text(code + "\n", encoding="utf-8")
    digest = sha256(code.encode("utf-8")).hexdigest()
    manifest = {
        "schema": "luna-arcade-ollama-candidate-v1",
        "title": "Luna Star Trail — experimental gameplay",
        "generated_by": "PRETRAINED_OLLAMA_MODEL",
        "model": model,
        "not_generated_by": ["MiniCoder scratch", "Luna MiniCoder V3"],
        "task": task,
        "code_sha256": digest,
        "syntax": "PASS_NODE_CHECK_ONLY",
        "behavior": "NOT_TESTED",
        "human_review_required": True,
        "engine_and_visuals_authored_by": "Human-authored reference",
        "generation_attempts": attempts,
        "code_executed_on_host": False,
        "source_provenance": "local pretrained Ollama model + original game contract",
        "files": [*ASSETS, "gameplay.js"],
        "warning": "Syntax and static filters do NOT prove safety or correct gameplay.",
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "status": "candidate_needs_human_review",
        "model": model,
        "attempts": attempts,
        "folder": str(folder),
        "candidate": str(folder / "gameplay.js"),
        "manifest": str(folder / "manifest.json"),
        "sha256": digest,
        "syntax": "pass",
        "behavior": "NOT_TESTED",
        "code_executed": False,
        "preview": "Review gameplay.js; then serve this folder on 127.0.0.1",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Luna Arcade local pretrained gameplay code generator")
    parser.add_argument("action", choices=("status", "build"))
    parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    parser.add_argument("--task", default="Smooth jumping, star pickups and slime patrol.")
    args = parser.parse_args()
    try:
        if args.action == "status":
            installed = installed_models()
            result = {
                "backend": "Ollama on 127.0.0.1:11434",
                "installed_models": installed,
                "recommended_model": DEFAULT_MODEL,
                "reference": str(DEMO / "index.html"),
                "reference_authored_manually": True,
            }
        else:
            installed = installed_models()
            if args.model not in installed:
                raise LocalModelError(
                    f"Model absent. Run: ollama pull {args.model}. "
                    f"Installed: {installed[:8]}"
                )
            result = build(args.task, args.model)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("status") == "rejected_no_preview":
            raise SystemExit(3)
    except (OSError, ValueError, LocalModelError) as exc:
        print(json.dumps({"status": "unavailable", "reason": str(exc),
                          "reference_untouched": True}, ensure_ascii=False, indent=2))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
