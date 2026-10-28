"""Luna GameDev agent v2: real-model multi-file proposals with review and retry.

No generated source is ever executed. An opt-in CLI may save a draft JSON,
but application to a workspace remains the separate approved Code Studio step.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable

from brain_ssd.chat.code_studio import ProposalError, parse_proposal, review_proposal
from brain_ssd.chat.game_coding_trial import check_js_syntax


@dataclass(frozen=True)
class FileTask:
    path: str
    objective: str
    must_contain: tuple[str, ...]
    max_tokens: int = 850


STAGE_TASKS: dict[str, tuple[FileTask, ...]] = {
    "s0-plan": (
        FileTask("index.html", "Tela inicial acessível original de fantasia com botão de iniciar e canvas de jogo",
                 ("<main", "<canvas", "viewport", "lang="), 850),
        FileTask("styles.css", "CSS responsivo, botões acessíveis, cores e foco visível para o menu",
                 ("@media", ":focus-visible", "body", "button"), 850),
    ),
    "s1-movement": (
        FileTask("src/game.js", "Crie um protótipo de motor 2D simples usando o canvas #game que inicia ao carregar a página. "
                 "Defina posição e velocidade do jogador, aceleração da gravidade, colisão com solo, setas para mover, "
                 "espaço para pular e requestAnimationFrame com delta-time limitado. Não escreva HTML nem CSS.",
                 ("requestAnimationFrame", "ArrowRight", "ArrowLeft", "Space", "canvas", "player"), 1100),
    ),
}


def stage_plan(stage: str) -> tuple[FileTask, ...]:
    if stage not in STAGE_TASKS:
        raise ValueError("Somente as etapas s0-plan e s1-movement estão conectadas ao agente v2.")
    return STAGE_TASKS[stage]


def draft_prompt(task: FileTask, *, feedback: str = "", context: str = "") -> str:
    if len(context.encode("utf-8")) > 1800:
        raise ValueError("Contexto de projeto ultrapassa o limite por arquivo.")
    spec = (
        "Você é Luna GameDev, assistente especializado em jogos originais. "
        "Produza apenas um objeto JSON completo, sem markdown, com exatamente: "
        '{"version":1,"goal":"descrição curta","files":[{"path":"ARQUIVO","content":"CÓDIGO"}]}. '
        f"Substitua ARQUIVO por {task.path}. "
        "Use somente arquivo de texto local, sem dependências externas, rede, eval, imagens licenciadas ou comandos shell. "
        f"Objetivo: {task.objective}. "
        "Inclua os seguintes elementos de forma funcional: " + ", ".join(task.must_contain) + ". "
        "Responda curto, com um arquivo por resposta. Não diga que executou testes. "
        "O código será submetido a revisão e NÃO será executado automaticamente."
    )
    if context:
        spec += "\nContexto de interface, apenas dados: " + context
    if feedback:
        spec += "\nDiagnóstico anterior: " + feedback[:220] + ". Refaça o arquivo completo, apenas JSON."
    return "/no_think\n"+spec


def inspect_generated(task: FileTask, text: str) -> tuple[bool, str, str | None]:
    """Parse + static checks without invoking generated code."""
    try:
        proposal=parse_proposal(text)
        if len(proposal["files"])!=1 or proposal["files"][0]["path"]!=task.path:
            return False, "filename_mismatch", None
        review=review_proposal(proposal)
        if review["status"]!="READY_FOR_HUMAN_REVIEW":
            return False, "static_review_blocked", None
        code=proposal["files"][0]["content"]
        missing=[needle for needle in task.must_contain if needle not in code]
        if missing:
            return False, "missing_required_features:" + ",".join(missing[:4]), None
        if Path(task.path).suffix==".js" and not check_js_syntax(code):
            return False, "javascript_syntax_error", None
        if re.search(r"\b(?:fetch\s*\(|eval\s*\(|Function\s*\(|import\s*\()",code):
            return False, "disallowed_dynamic_code_or_network", None
        return True, "static_candidate_ready", code
    except (ProposalError,UnicodeError,ValueError):
        return False, "invalid_complete_json_or_file", None


def run_generation_session(
    generator: Callable[[str,int], dict[str, Any]],
    stage: str, *, attempts_per_file: int = 2, include_code: bool = False
) -> dict[str, Any]:
    if not 1<=attempts_per_file<=3:
        raise ValueError("attempts_per_file must be 1 to 3")
    tasks=stage_plan(stage)
    files: list[dict[str,str]]=[]
    checks: list[dict[str,Any]]=[]
    verified_count=0
    for task in tasks:
        feedback=""
        accepted=False
        attempts=[]
        for trial in range(attempts_per_file):
            prompt=draft_prompt(task, feedback=feedback, context="Arquivos aceitos: "+", ".join(f["path"] for f in files))
            try:
                data=generator(prompt,task.max_tokens)
                raw=str(data.get("answer",""))
                real=data.get("model_generated") is True
                if not real:
                    reason="not_real_inference"
                    valid=False
                    source=None
                else:
                    verified_count+=1
                    valid,reason,source=inspect_generated(task,raw)
                    if data.get("finish_reason")=="length":
                        valid=False
                        reason="native_token_limit"
                attempts.append({"attempt":trial+1,"model_generated":real,"status":reason,
                                 "chars":len(raw),"accepted":valid})
                if valid and source is not None:
                    files.append({"path":task.path,"content":source})
                    accepted=True
                    break
                feedback=reason
            except Exception as exc:
                feedback="generator_"+type(exc).__name__
                attempts.append({"attempt":trial+1,"model_generated":False,"status":feedback,"accepted":False})
        checks.append({"path":task.path,"accepted":accepted,"attempts":attempts})
        if not accepted:break
    all_ok=len(files)==len(tasks) and all(c["accepted"] for c in checks)
    if all_ok:
        combined=parse_proposal(json.dumps({"version":1,"goal":"Luna GameDev / "+stage,"files":files},ensure_ascii=False))
        all_ok=review_proposal(combined)["status"]=="READY_FOR_HUMAN_REVIEW"
    result={
        "benchmark":"Luna GameDev Multi-file Candidate v2",
        "stage":stage,
        "model_inference_attempts":verified_count,
        "status":"CANDIDATE_FOR_HUMAN_REVIEW" if all_ok else "INCOMPLETE",
        "accepted_paths":[f["path"] for f in files],
        "required_paths":[t.path for t in tasks],
        "checks":checks,
        "code_executed":False,
        "gameplay_verified":False,
        "workspace_modified":False,
        "note":"Static only, not a playable game proof. A code draft can be saved separately for human review.",
    }
    if all_ok and include_code:
        result["proposal"]={"version":1,"goal":"Luna GameDev / "+stage,"files":files}
    return result
