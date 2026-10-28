#!/usr/bin/env python3
"""Real Qwen second attempt, based exclusively on its own prior game and browser bugs.

Changes only the game.js authored by Qwen; HTML/CSS preserved byte-for-byte.
No assistant-provided gameplay code or fallback. No execution during inference.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json,os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.backend import GenerationRequest
from brain_ssd.chat.runtime import LocalChatRuntime
from brain_ssd.local_runtime.pipeline import clean_answer
from generate_luna_original_game import verify_file,node_check,SCENE

BASE=ROOT/"results"/"luna-original-candidate"
OUT=ROOT/"results"/"luna-original-repair"
BUGS = (
    "O Playwright detectou 2 falhas graves na primeira versão que VOCÊ escreveu: "
    "(1) teclas de pulo e ataque não funcionam porque KeyboardEvent foi comparado "
    "de forma errada: use event.code === 'Space' e event.code === 'KeyZ'. "
    "(2) o jogo declarou vitória em wave 2 sem derrotar um verdadeiro chefe "
    "e sem ter três ondas. O requisito é wave=1 e wave=2 com inimigos normais, "
    "wave=3 com boss de vida 150+; vitória APENAS quando hp do boss chegar a 0. "
    "Outros defeitos encontrados por revisão: usar splice(i,1) onde i não foi declarado "
    "no escopo do ataque é incorreto; nunca remover inimigos por saírem do mapa; "
    "seleção da classe não deve ser forçada para 'melee'; evitar loops duplicados no restart. "
    "A primeira versão gerou game.js mas só 2/4 testes de browser passaram."
)
PROMPT=(
    "/no_think\nVocê é Luna GameDev. Reescreva a lógica completa de SEU "
    "jogo original Luna: Constelação Perdida com essas correções, "
    "não reutilize nem importe código do site/arcade, não mostre JSON nem markdown. "
    "Responda SOMENTE JavaScript bruto válido para game.js. "
    "HTML já é seu e contém canvas#game 960x540, button#start, select#hero "
    "com melee/ranged/magic, p#status, link CSS. "
    "Precisa inicializar por clique, executar loop requestAnimationFrame contínuo, "
    "usar delta time limitado, colisão com solo em y=440 e gravidade, setas, "
    "pulo Space e ataque KeyZ, vida e dano, invulnerabilidade temporária, "
    "enemies e boss com HP, três ondas reais, derrota e vitória só após boss morto, "
    "status HUD e botão para reinício. "
    "As três classes devem ter dano e vida diferentes. "
    "Ataque corpo-a-corpo e habilidades à distância podem ser simples mas reais. "
    "Na fase 1 deve existir ao menos um inimigo ao iniciar. "
    "Disponibilize window.__LUNA_ORIGINAL_QA__={snapshot:()=>({mode,player:"
    "{x:player.x,y:player.y,hp:player.hp},wave,enemies:"
    "enemies.map(e=>({x:e.x,hp:e.hp,boss:e.boss}))})}. "
    "Desenhe personagens, cenário, números e feedback visual diretamente em ctx, "
    "com arte original. Sem bibliotecas, recursos externos, fetch, eval, import, "
    "armazenamento nem APIs de rede. "
    "OBRIGATÓRIO: e.code === 'Space', e.code === 'KeyZ', "
    "wave === 3, mode='victory' após derrotar boss, "
    "não usar variáveis de loop fora do escopo. "
    "Escreva concisamente. \n\nERROS ANTERIORES:\n"+BUGS
)

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--retries",type=int,choices=(1,2,3),default=2)
    p.add_argument("--model-file",default="Qwen3-4B-Q4_K_M.gguf")
    args=p.parse_args()
    if os.name!="nt":
        print("Actual Windows Qwen required",file=sys.stderr)
        return 2
    OUT.mkdir(parents=True,exist_ok=True)
    report={"benchmark":"Luna Self-Repair Complete Game v2","model":args.model_file,
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"ERROR","source_model_verified":False,"gameplay_verified":False,
            "assistant_gameplay_code_used":False,"code_executed":False,"attempts":[]}
    runtime=None
    try:
        provenance=json.loads((BASE/"provenance.json").read_text(encoding="utf-8"))
        assert provenance["generation_complete"] is True
        for name in ("index.html","styles.css","game.js"):
            data=(BASE/name).read_bytes().replace(b"\r\n",b"\n")
            assert sha256(data).hexdigest()==provenance["provenance_sha256"][name]
            if name!="game.js":
                (OUT/name).write_bytes(data)
        original=(BASE/"game.js").read_text(encoding="utf-8")
        report["source_sha256"]=sha256(original.replace("\r\n","\n").encode()).hexdigest()
        runtime=LocalChatRuntime(ROOT,profile="equilibrado",model_file=args.model_file)
        feedback=""
        for trial in range(args.retries):
            prompt=PROMPT+("\nÚltima revisão reprovou: "+feedback[:240]+". Reescreva o arquivo inteiro, sem explicações." if feedback else "")
            raw_response=runtime.core_backend.generate(GenerationRequest(
                prompt=prompt,max_tokens=2800,temperature=0.12))
            if raw_response.get("return_code")!=0:
                feedback="native_inference_failure"
                report["attempts"].append({"real_model":False,"reason":feedback})
                continue
            answer=clean_answer(str(raw_response.get("stdout") or ""))
            ok,reason,s=verify_file("game.js",answer,js_check=node_check)
            report["attempts"].append({"real_model":bool(answer),"accepted":ok,
                                       "reason":reason,"chars":len(answer)})
            if not ok:
                feedback=reason
                (OUT/"latest-rejected.js.txt").write_bytes(answer.encode("utf-8"))
                continue
            if not ("e.code" in s and "wave === 3" in s):
                feedback="missing_fixed_keycode_or_three_wave_condition"
                report["attempts"][-1]["accepted"]=False
                report["attempts"][-1]["reason"]=feedback
                continue
            (OUT/"game.js").write_bytes(s.encode("utf-8"))
            report["status"]="STATIC_REPAIR_CANDIDATE"
            report["source_model_verified"]=True
            report["provenance_sha256"]={name:sha256((OUT/name).read_bytes()).hexdigest()
                                          for name in ("index.html","styles.css","game.js")}
            return 0
        report["status"]="INCOMPLETE"
        return 1
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        return 2
    finally:
        if runtime is not None:runtime.close()
        (OUT/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    raise SystemExit(main())
