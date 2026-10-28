#!/usr/bin/env python3
"""Have real Luna/Qwen author a second, usable game stylesheet without borrowing styles."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json,os,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.pipeline import clean_answer

SOURCE=ROOT/"results"/"luna-original-refined"
OUT=ROOT/"results"/"luna-original-style"
SOURCE_RUN=40647732624
TASK=(
    "/no_think\nVocê é Luna, autora do jogo original Luna: Constelação Perdida. "
    "Reescreva o SEU styles.css do ZERO com CSS CURTO, seguro, bonito, simples e RESPONSIVO. "
    "Responda SOMENTE CSS, sem markdown, sem HTML, sem explicação. "
    "HTML fixo: body > main > h1, p#status, select#hero, button#start, canvas#game (960x540). "
    "FALHA ANTERIOR: select#hero e button#start tinham position:absolute com "
    "top:50%, left:50%, ficando UM SOBRE O OUTRO e impossibilitando clicar. "
    "NOVA REGRA: NÃO use position:absolute, position:fixed, transform:translate "
    "nos controles ou canvas. Use main{display:flex; flex-direction:column; "
    "align-items:center; gap:14px;} e body{overflow:auto;min-height:100vh;}. "
    "Canvas: posição normal, width:100%, max-width:960px, height:auto; "
    "acima o título, status, select e botão cada um na própria linha. "
    "Design: cores noturnas índigo e violeta com accent dourado, "
    "fundo radial-gradient, tipografia system-ui, cartões e bordas leves, "
    "botões elegantes. Use seletor explícito #start e #hero. "
    "Obrigatório usar: body, main, canvas, #start, #hero, #status, "
    ":focus-visible e @media (max-width:600px). "
    "Permita rolagem mobile, bom contraste, sem sobreposição. "
    "CRÍTICO: NÃO USE absolutamente nenhum url(, @import, @font-face, "
    "https, http, imagem, SVG, data URI, resource externo, script ou font. "
    "Todo estilo deve ser CSS puro com gradientes e cores hexadecimais. "
    "Máximo 110 linhas CSS."
)
REQ=("body","main","canvas","#start","#hero","#status",":focus-visible","@media")
BANNED=re.compile(r"@import\b|url\s*\(|https?://|javascript:|expression\s*\(|"
                  r"<script|@font-face",re.I)

def validate_css(source:str)->tuple[bool,str,str]:
    if not isinstance(source,str) or not 100<len(source)<25000:
        return False,"empty_or_excessive",""
    text=source.strip()
    m=re.fullmatch(r"\x60\x60\x60css\s*\n(.*?)\n\x60\x60\x60",text,re.I|re.S)
    if m:text=m.group(1).strip()
    if BANNED.search(text):
        return False,"external_or_dynamic_css",""
    missing=[token for token in REQ if token not in text]
    if missing:
        return False,"missing_css_contract:"+",".join(missing),""
    if re.search(r"body\s*\{[^}]*overflow\s*:\s*hidden",text,re.I|re.S):
        return False,"mobile_body_scroll_disabled",""
    return True,"static_css_candidate",text+"\n"

def digest(blob:bytes)->str:
    return sha256(blob).hexdigest()

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    p.add_argument("--model-file",default="Qwen3-4B-Q4_K_M.gguf")
    args=p.parse_args()
    if os.name!="nt":
        print("Real Qwen Windows required",file=sys.stderr)
        return 2
    OUT.mkdir(parents=True,exist_ok=True)
    report={"status":"ERROR","source_run":SOURCE_RUN,"model":args.model_file,
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "gameplay_verified":False,"visual_verified":False,
            "assistant_css_code_used":False,"attempts":[]}
    engine=None
    try:
        provenance=json.loads((SOURCE/"provenance.json").read_text(encoding="utf-8"))
        assert provenance["status"]=="STATIC_REFINED_CANDIDATE"
        for name in ("index.html","styles.css","game.js"):
            data=(SOURCE/name).read_bytes().replace(b"\r\n",b"\n")
            assert digest(data)==provenance["provenance_sha256"][name],name
            if name!="styles.css":
                (OUT/name).write_bytes(data)
        from brain_ssd.chat.runtime import LocalChatRuntime
        engine=LocalChatRuntime(ROOT,profile="equilibrado",model_file=args.model_file)
        feedback=""
        for i in range(args.attempts):
            reply=engine.core_backend.generate(GenerationRequest(
                prompt=TASK+("\nERRO ANTERIOR: "+feedback+". Reescreva o CSS completo." if feedback else ""),
                max_tokens=900,temperature=0.15))
            if reply.get("return_code")!=0:
                feedback="native_inference_failed"
                report["attempts"].append({"attempt":i+1,"real":False,"reason":feedback})
                continue
            answer=clean_answer(str(reply.get("stdout") or ""))
            (OUT/("model-css-attempt-"+str(i+1)+".txt")).write_bytes(answer.encode("utf-8"))
            ok,reason,css=validate_css(answer)
            report["attempts"].append({"attempt":i+1,"real":bool(answer),"accepted":ok,
                                        "reason":reason,"characters":len(answer)})
            if ok:
                (OUT/"styles.css").write_bytes(css.encode("utf-8"))
                report["status"]="STATIC_CSS_CANDIDATE"
                report["model_authored_styles"]=True
                report["provenance_sha256"]={name:digest((OUT/name).read_bytes())
                                              for name in ("index.html","styles.css","game.js")}
                return 0
            feedback=reason
        report["status"]="INCOMPLETE"
        return 1
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        return 2
    finally:
        if engine is not None:engine.close()
        (OUT/"provenance.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)

if __name__=="__main__":
    raise SystemExit(main())
