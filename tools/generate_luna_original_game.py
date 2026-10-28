#!/usr/bin/env python3
"""Luna-authored game generator: *all three game files must come from real Qwen*.

The assistant provides prompts, constraints, security gate and test harness;
it never supplies replacement game, CSS or HTML in the output directory.
No generated file is executed during inference.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Callable, Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.pipeline import clean_answer

OUT = ROOT/"results"/"luna-original-candidate"
GAME_NAME = "Luna: Constelação Perdida"
SCENE = (
    "Crie um jogo autoral 2D de ação/plataformas para navegador, independente de "
    "Grand Chase e dos arquivos de site/arcade. Três classes: Kael espadachim, "
    "Lyra arqueira, Orin mago; seleção inicial de classe. Três ondas de inimigos "
    "e um chefe final na terceira onda. Controles ←→, Space para pular, "
    "Z para atacar; HP do jogador e dos inimigos; derrota, vitória e reinício. "
    "Arte feita com Canvas e CSS, sem imagens/músicas/serviços externos. "
    "Esta é sua criação completa; não altere nem importe o jogo de referência."
)
TASKS = {
"index.html": (
    "Você é a Luna GameDev, criadora de jogos. Responda SOMENTE HTML completo, "
    "sem markdown, sem explicações. Crie a interface de 'Luna: Constelação Perdida', "
    "um jogo indie 2D bonito e distinto. Precisa de <!doctype html>, "
    '<html lang="pt-BR">, <meta name="viewport" content="width=device-width,initial-scale=1">, '
    '<link rel="stylesheet" href="styles.css">, '
    '<script src="game.js" defer></script>, '
    '<main>, <canvas id="game" width="960" height="540"></canvas>, '
    '<button id="start">Iniciar aventura</button>, '
    '<select id="hero"><option value="melee">Kael</option><option value="ranged">Lyra</option>'
    '<option value="magic">Orin</option></select>, '
    '<p id="status">Selecione um herói</p>. '
    "Não inclua JavaScript inline, handlers onClick, fontes remotas ou CDN. "
    "HTML curto e acessível. Estilo visual será fornecido por styles.css separado."
),
"styles.css": (
    "Você é a Luna GameDev. Responda APENAS CSS original sem markdown. "
    "Crie uma interface de jogo indie muito bonita, fundo de céu noturno, "
    "efeitos de brilho, cores memoráveis, layout responsivo. "
    "HTML contém body, main, canvas#game, button#start, select#hero, p#status. "
    "Inclua @media(max-width:600px) e regras :focus-visible para acessibilidade. "
    "Canvas se adapta à largura sem deformar; contraste bom. "
    "Código 100% original, sem imports ou URL externas."
),
"game.js": (
    "Você é a Luna GameDev. Entregue APENAS UM ARQUIVO JavaScript completo e válido, "
    "sem markdown, sem JSON e sem explicações. É para um jogo Canvas 2D original. "
    "A página tem <canvas id='game' width='960' height='540'>, "
    "<button id='start'>, <select id='hero'> com valores melee,ranged,magic "
    "e <p id='status'>. "
    "Use const canvas=document.getElementById('game'), ctx=canvas.getContext('2d'). "
    "Crie um objeto player com x,y,vx,vy,hp; um array enemies com hp; uma variável wave. "
    "Botão start reinicia o jogo e lê a classe. "
    "ArrowLeft e ArrowRight movem com velocidade; Space pula apenas no chão; "
    "KeyZ ataca inimigos próximos, ou projéteis nas classes de alcance. "
    "Gravidade, colisão com chão, invulnerabilidade breve, inimigos se aproximando e "
    "ferindo player, morte e tela de derrota. Ao eliminar todos os inimigos, "
    "passe para a próxima onda, três ondas ao todo. Na terceira onda surge um "
    "boss mais forte. Quando derrotar o boss, defina o estado 'victory' "
    "e desenhe 'VITÓRIA' na tela e mostre no status. "
    "Chame requestAnimationFrame continuamente com delta-time limitado. "
    "Desenhe cenário e personagens com primitivas Canvas (rect, circle, texto), "
    "incluindo animações visuais simples. "
    "Disponibilize para os testes uma API SOMENTE de leitura: "
    "window.__LUNA_ORIGINAL_QA__={snapshot:()=>({mode,player:{x:player.x,y:player.y,hp:player.hp},wave,enemies:enemies.map(e=>({x:e.x,hp:e.hp,boss:e.boss}))})}; "
    "Use as strings literais 'ArrowRight', 'ArrowLeft', 'Space', 'KeyZ', 'victory' e 'boss'. "
    "NÃO use import/export, eval, fetch, WebSocket, setInterval ou dependências. "
    "Escreva JavaScript conciso e válido, sem HTML, com toda a lógica jogável."
)
}
TOKENS = {"index.html":950,"styles.css":1050,"game.js":2600}
MUST = {
"index.html":('<!doctype html','lang="pt-BR"','name="viewport"','id="game"','id="start"','id="hero"','id="status"','styles.css','game.js'),
"styles.css":('body','canvas',':focus-visible','@media'),
"game.js":('canvas','getContext','player','enemies','wave','ArrowRight','ArrowLeft','Space','KeyZ','victory','boss','requestAnimationFrame','__LUNA_ORIGINAL_QA__')
}
BLOCKED = re.compile(
    r"\b(?:fetch|eval|Function|WebSocket|XMLHttpRequest|Worker|SharedWorker|importScripts)\s*\("
    r"|\b(?:localStorage|sessionStorage|indexedDB)\b|\bimport\s*\(|\brequire\s*\("
    r"|https?://|<script[^>]+src\s*=\s*['\"]https?:",re.I
)


def unwrap(source: str, kind: str) -> str:
    if not source or len(source)>42000:
        raise ValueError("empty_or_excessively_long")
    s=source.strip()
    if re.search(r"<think>|</think>",s,re.I):
        raise ValueError("exposed_reasoning")
    tags={"index.html":"html","styles.css":"css","game.js":"javascript"}
    tag=tags[kind]
    pattern=r"^\x60\x60\x60(?:"+tag+r"|js)?\s*\n(.*?)\n\x60\x60\x60$"
    m=re.fullmatch(pattern,s,re.I|re.S)
    return (m.group(1) if m else s).strip()+"\n"


def verify_file(name: str, source: str, *, js_check:Callable[[str],bool]) -> tuple[bool,str,str]:
    try:
        s=unwrap(source,name)
    except ValueError as exc:
        return False,str(exc),""
    if BLOCKED.search(s):
        return False,"blocked_external_api_or_url",""
    missing=[term for term in MUST[name] if term.lower() not in s.lower()]
    if missing:
        return False,"missing_contract:"+",".join(missing[:4]),""
    if name=="index.html":
        if re.search(r"\bon[a-z]+\s*=",s,re.I) or re.search(r"<script(?![^>]*src=)",s,re.I):
            return False,"inline_script_or_events_disallowed",""
    if name=="game.js" and not js_check(s):
        return False,"javascript_syntax_error",""
    return True,"static_candidate",s


def node_check(text:str)->bool:
    with tempfile.TemporaryDirectory(prefix="luna-code-") as folder:
        path=Path(folder)/"generated.js"
        path.write_text(text,encoding="utf-8")
        try:
            r=subprocess.run(["node","--check",str(path)],capture_output=True,
                             timeout=12,check=False)
            return r.returncode==0
        except (OSError,subprocess.TimeoutExpired):
            return False


def generate_all(infer:Callable[[str,int],dict[str,Any]], *, retries:int=2,
                 js_check:Callable[[str],bool]=node_check)->tuple[dict[str,Any],dict[str,str]]:
    if not 1<=retries<=3:
        raise ValueError("retries must be between 1 and 3")
    output={}
    details=[]
    for name,prompt in TASKS.items():
        feedback=""
        trials=[]
        for attempt in range(retries):
            request="/no_think\n"+SCENE+"\n"+prompt
            if feedback:
                request+="\nSeu arquivo anterior falhou: "+feedback+". Escreva novamente o arquivo COMPLETO e corrija."
            try:
                result=infer(request,TOKENS[name])
                real=result.get("model_generated") is True
                raw=str(result.get("answer") or "")
                if real:
                    accepted,reason,content=verify_file(name,raw,js_check=js_check)
                else:
                    accepted,reason,content=False,"not_real_model",""
                if result.get("finish_reason")=="length":
                    accepted,reason=False,"native_token_limit"
                trials.append({"attempt":attempt+1,"real_model":real,"accepted":accepted,
                               "reason":reason,"characters":len(raw)})
                if accepted:
                    output[name]=content
                    break
                feedback=reason
            except Exception as exc:
                feedback="runtime_"+type(exc).__name__
                trials.append({"attempt":attempt+1,"real_model":False,"accepted":False,
                               "reason":feedback})
        details.append({"file":name,"accepted":name in output,"attempts":trials})
        if name not in output:
            break
    accepted_all=len(output)==len(TASKS)
    report={"benchmark":"Luna Original Complete Game Attempt v1",
            "author":"Qwen3-4B-Q4_K_M.gguf (raw native inference)",
            "game":GAME_NAME,
            "required_files":list(TASKS),
            "accepted_files":list(output),
            "provenance_sha256":{name:hashlib.sha256(code.encode("utf-8")).hexdigest() for name,code in output.items()},
            "requests":details,
            "generation_complete":accepted_all,
            "status":"STATIC_CANDIDATE" if accepted_all else "INCOMPLETE",
            "gameplay_verified":False,"visual_verified":False,
            "deployed":False,"reference_code_copied":False,
            "note":"All output files originate only from Qwen. Browser playtesting and human review are mandatory before describing this as a complete playable game."}
    return report,output


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--model-file",default="Qwen3-4B-Q4_K_M.gguf")
    p.add_argument("--retries",type=int,choices=(1,2,3),default=2)
    args=p.parse_args()
    if os.name!="nt":
        print("Real Windows GGUF environment required; mocks are never published.",file=sys.stderr)
        return 2
    from brain_ssd.chat.runtime import LocalChatRuntime
    OUT.mkdir(parents=True,exist_ok=True)
    engine=None
    report={"status":"ERROR","created_utc":datetime.now(timezone.utc).isoformat()}
    try:
        engine=LocalChatRuntime(ROOT,profile="equilibrado",model_file=args.model_file)
        def infer(prompt:str,n:int)->dict[str,Any]:
            response=engine.core_backend.generate(GenerationRequest(
                prompt=prompt,max_tokens=n,temperature=0.15))
            if response.get("return_code")!=0:
                raise RuntimeError("native_inference_error")
            raw=clean_answer(str(response.get("stdout") or ""))
            return {"answer":raw,"model_generated":bool(raw),
                    "finish_reason":(response.get("metrics") or {}).get("finish_reason")}
        report,files=generate_all(infer,retries=args.retries)
        for name,source in files.items():
            (OUT/name).write_text(source,encoding="utf-8")
        return 0 if report["generation_complete"] else 1
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        return 2
    finally:
        if engine is not None:
            engine.close()
        (OUT/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    raise SystemExit(main())
