#!/usr/bin/env python3
"""Real Qwen patch-by-patch repair of Qwen's own original game.

This script contains NO replacement game code and never executes model output.
Every modified substring must originate in a genuine native Qwen response.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from generate_luna_original_game import node_check, verify_file
from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.pipeline import clean_answer

ORIGINAL = ROOT / "results" / "luna-original-candidate"
OUTPUT = ROOT / "results" / "luna-original-targeted"
REFERENCE_RUN = 40636116071
RULES = (
    "Você é Luna GameDev; foi VOCÊ quem escreveu o jogo original, não o ChatGPT. "
    "Receberá um trecho específico do seu código e um bug encontrado por Chromium. "
    "Responda SOMENTE JavaScript substituto do trecho, SEM markdown, SEM comentários externos, "
    "SEM a palavra 'Explicação', SEM import, fetch, eval, HTML ou scripts remotos. "
    "Pode usar variáveis já presentes no escopo (player, enemies, wave, mode, "
    "attackTarget, isAttacking, attackTimer, status). NÃO reescreva todo o jogo."
)
TASKS = [
    {
        "id": "jump_code",
        "start": "e.key === 'Space'",
        "end": None,
        "goal": "Esta comparação usa e.key, mas Playwright pressiona a tecla Space por KeyboardEvent.code. "
                "Retorne apenas a expressão JavaScript booleana corrigida que identifica Space usando e.code.",
        "requires": ("e.code", "Space"),
        "max_tokens": 100,
    },
    {
        "id": "attack_code",
        "start": "e.key === 'KeyZ'",
        "end": None,
        "goal": "Esta comparação usa e.key, mas Playwright pressiona Z e o código físico é KeyZ. "
                "Retorne apenas a expressão booleana correta para e.code.",
        "requires": ("e.code", "KeyZ"),
        "max_tokens": 100,
    },
    {
        "id": "combat_logic",
        "start": "    // Attack\n",
        "end": "    // Enemy movement\n",
        "goal": "Reescreva SOMENTE o bloco de ataque dentro da função gameLoop(). "
                "Se isAttacking e attackTarget existem, aplique dano ao inimigo próximo "
                "sem repetir ataque por frame indefinidamente; use attackTimer para controlar. "
                "Se hp <= 0, remova inimigo corretamente usando enemies.filter() ou indexOf() "
                "(NUNCA splice(i,1) com i não declarado). Use player.x, player.y, "
                "attackRange, isAttacking e attackTarget; mantenha jogo sem exceções. "
                "Retorne JavaScript do bloco diretamente, sem chaves da função externa.",
        "requires": ("isAttacking", "attackTarget", "hp", "enemies"),
        "max_tokens": 520,
    },
    {
        "id": "wave_progression",
        "start": "    // Check for victory\n",
        "end": "    // Check for defeat\n",
        "goal": "Reescreva APENAS o primeiro bloco de progressão para TRÊS ondas reais. "
                "O jogo começa wave=0 e enemies vazio. Quando zero inimigos vivos: "
                "wave=1 cria pelo menos um inimigo comum; quando terminam, wave=2 cria "
                "mais inimigos comuns; quando terminam, wave=3 cria um único boss "
                "com hp >= 150 e y=420 ao alcance do jogador. "
                "Não declare vitória neste bloco; isso será checado separadamente. "
                "Use enemies.push({x:...,y:420,hp:...,boss:false/true}). "
                "NUNCA repita o spawn em loop quando enemies já tiver inimigos. "
                "Retorne somente o código da progressão, sem o marcador de Check for defeat.",
        "requires": ("wave", "enemies", "boss", "3", "push"),
        "max_tokens": 540,
    },
    {
        "id": "victory_gate",
        "start": "    // Check for victory\n",
        "end": "    // Update status\n",
        "goal": "Substitua somente o bloco FINAL de detecção de vitória, dentro de gameLoop(). "
                "Vitória APENAS quando wave === 3 E o boss (que aparece na wave3) "
                "está derrotado, isto é, enemies.length === 0 após matar o boss. "
                "Nesse caso mode='victory', status.textContent='VITÓRIA' e return; "
                "caso contrário não altere mode. O bloco vai antes de Update status. "
                "Retorne o bloco JavaScript de verificação, sem marcadores.",
        "requires": ("wave", "3", "enemies", "victory", "return"),
        "max_tokens": 260,
    },
]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalize(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n")


def region(code: str, task: dict[str, Any]) -> tuple[str, str, str]:
    start = task["start"]
    end = task["end"]
    if task["id"] in ("victory_gate", "wave_progression"):
        indices = [m.start() for m in re.finditer(re.escape(start), code)]
        expected = 2 if task["id"] == "wave_progression" else 1
        if len(indices) != expected:
            raise ValueError("victory_marker_count_mismatch")
        pos = indices[0]
    else:
        if code.count(start) != 1:
            raise ValueError("source_marker_not_unique:" + task["id"])
        pos = code.index(start)
    if end is None:
        return code[:pos], code[pos:pos+len(start)], code[pos+len(start):]
    stop = code.find(end, pos+len(start))
    if stop == -1:
        raise ValueError("closing_marker_missing:" + task["id"])
    return code[:pos], code[pos:stop], code[stop:]


def sanitize_model_piece(raw: str, task: dict[str, Any]) -> tuple[bool, str, str]:
    text = str(raw).strip()
    if not 5 < len(text) < 4500 or "\x00" in text:
        return False, "invalid_size", ""
    fence = re.fullmatch(r"\x60\x60\x60(?:javascript|js)?\s*\n(.*?)\n\x60\x60\x60", text, re.S|re.I)
    if fence:
        text = fence.group(1).strip()
    blocked = re.search(r"<script|</script>|https?://|\b(?:fetch|eval|Function|"
                        r"WebSocket|XMLHttpRequest|Worker|require|import)\s*\(|"
                        r"\b(?:globalThis|localStorage|indexedDB)\b", text, re.I)
    if blocked:
        return False, "prohibited_api", ""
    missing = [word for word in task["requires"] if word not in text]
    if missing:
        return False, "missing_contract:" + ",".join(missing), ""
    if task["end"] is None and ("\n" in text or ";" in text or "{" in text):
        return False, "expression_not_single", ""
    if task["id"] == "wave_progression" and ("mode =" in text or "mode=" in text):
        return False, "wave_spawn_must_not_declare_victory", ""
    return True, "static_patch_candidate", text


def generate_patches(
    original: str,
    infer: Callable[[str, int], dict[str, Any]],
    *,
    attempts: int = 2,
    checker: Callable[[str], bool] = node_check
) -> tuple[dict[str, Any], str | None]:
    """Patch fragments from actual model, no assistant-generated code."""
    if not 1 <= attempts <= 3:
        raise ValueError("invalid_attempts")
    state = original
    history = []
    for task in TASKS:
        prefix, old, suffix = region(state, task)
        feedback = ""
        accepted = False
        trials = []
        for n in range(attempts):
            prompt = ("/no_think\n" + RULES + "\nERRO: " + task["goal"] +
                      "\nTRECHO ORIGINAL (substitua exatamente este trecho):\n" + old.strip() +
                      ("\nFALHA ANTERIOR: " + feedback if feedback else "") +
                      "\nRESPOSTA: somente o código substituto.")
            try:
                response = infer(prompt, task["max_tokens"])
                answer = str(response.get("answer") or "")
                real = response.get("model_generated") is True
                if not real:
                    valid, reason, piece = False, "not_native_model", ""
                else:
                    valid, reason, piece = sanitize_model_piece(answer, task)
                    if response.get("finish_reason") == "length":
                        valid, reason = False, "token_limit"
                    if valid:
                        proposed = prefix + piece + ("\n" if task["end"] is not None else "") + suffix
                        if not checker(proposed):
                            valid, reason = False, "javascript_syntax_error"
                trials.append({"attempt":n+1, "model_generated":real, "accepted":valid,
                               "reason":reason, "answer_chars":len(answer),
                               "candidate_excerpt":answer[:1200]})
                if valid:
                    state = proposed
                    accepted = True
                    break
                feedback = reason
            except Exception as exc:
                feedback = "native_" + type(exc).__name__
                trials.append({"attempt":n+1, "model_generated":False,
                               "accepted":False,"reason":feedback})
        history.append({"task":task["id"], "accepted":accepted,"attempts":trials})
        if not accepted:
            break
    good = len(history)==len(TASKS) and all(item["accepted"] for item in history)
    return {
        "benchmark":"Luna Genuine Model Self-Repair Patches v3",
        "source_run":REFERENCE_RUN,
        "source_sha256":sha(original.encode("utf-8")),
        "tasks":history,
        "patches_accepted":len([p for p in history if p["accepted"]]),
        "required_patches":len(TASKS),
        "status":"STATIC_PATCHED_CANDIDATE" if good else "INCOMPLETE",
        "model_only_patch_content":True,
        "gameplay_verified":False,
        "assistant_gameplay_code_used":False,
    }, state if good else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-file", default="Qwen3-4B-Q4_K_M.gguf")
    parser.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    args=parser.parse_args()
    if os.name != "nt":
        print("Windows real-Qwen run required",file=sys.stderr)
        return 2
    OUTPUT.mkdir(parents=True,exist_ok=True)
    report = {"status":"ERROR","created_utc":datetime.now(timezone.utc).isoformat()}
    engine = None
    try:
        reference=json.loads((ORIGINAL/"provenance.json").read_text(encoding="utf-8"))
        assert reference["generation_complete"] is True
        for name in ("index.html","styles.css","game.js"):
            data=normalize((ORIGINAL/name).read_bytes())
            assert sha(data)==reference["provenance_sha256"][name],name
            if name!="game.js":
                (OUTPUT/name).write_bytes(data)
        original=normalize((ORIGINAL/"game.js").read_bytes()).decode("utf-8")
        from brain_ssd.chat.runtime import LocalChatRuntime
        engine=LocalChatRuntime(ROOT,profile="equilibrado",model_file=args.model_file)
        def infer(prompt:str,max_tokens:int) -> dict[str,Any]:
            reply=engine.core_backend.generate(GenerationRequest(
                prompt=prompt, max_tokens=max_tokens, temperature=0.1))
            if reply.get("return_code")!=0:
                raise RuntimeError("native_inference_failed")
            answer=clean_answer(str(reply.get("stdout") or ""))
            return {"answer":answer,"model_generated":bool(answer),
                    "finish_reason":(reply.get("metrics") or {}).get("finish_reason")}
        report,patched=generate_patches(original,infer,attempts=args.attempts)
        report["model"]=args.model_file
        if patched is not None:
            valid,why,_=verify_file("game.js",patched,js_check=node_check)
            if not valid:
                report["status"]="INCOMPLETE"
                report["final_review_reason"]=why
                return 1
            (OUTPUT/"game.js").write_bytes(patched.encode("utf-8"))
            report["provenance_sha256"]={name:sha((OUTPUT/name).read_bytes())
                                          for name in ("index.html","styles.css","game.js")}
            report["status"]="STATIC_PATCHED_CANDIDATE"
            return 0
        return 1
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        return 2
    finally:
        if engine is not None:engine.close()
        (OUTPUT/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    raise SystemExit(main())
