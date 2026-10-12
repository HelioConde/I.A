"""Deterministic Luna answers for clock, runtime identity and saved chat facts.

These routes do not access web, model weights or permanent episodic memory.
Never infer an absent historical message from the Qwen's limited context.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

_WEEKDAYS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
             "sexta-feira", "sábado", "domingo")
_MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
           "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def _text(value: str) -> str:
    lowered = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(c for c in lowered if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[,;:]+", " ", normalized)).strip(" ?!.")


def is_first_question_intent(question: str) -> bool:
    t = _text(question)
    return bool(re.search(r"\b(?:primeira|primeiro)\b", t)
                and re.search(r"\b(?:pergunta|mensagem)\b", t)
                and re.search(r"\b(?:fiz|enviei|disse|conversa|chat)\b", t))


def _result(message: str, action: str) -> dict[str, Any]:
    return {
        "answer": message, "mode": "local_command",
        "local_action": action, "source": "local_verified_session",
        "metrics": {}, "active_pages": 0, "sources_from_ssd": 0,
        "episodic_memories_used": 0, "episodic_ambiguities_detected": 0,
        "episodic_ambiguities_withheld": False, "cognitive_shadow": None,
        "note": "Resposta local determinística; o Qwen não foi consultado.",
    }


def answer_session_fact(
    question: str, raw_history: Any, *, model_name: str,
    runtime_ready: bool, first_question: str | None = None,
    clock: datetime | None = None,
) -> dict[str, Any] | None:
    if not isinstance(question, str):
        return None
    q = _text(question)
    if not q:
        return None
    if re.fullmatch(
        r"(?:voce sabe )?(?:qual (?:e |eh )?a? ?data de hoje|"
        r"que dia (?:e|eh) hoje|qual (?:e|eh) o dia de hoje|"
        r"qual (?:e|eh) a data atual|em que dia estamos hoje)",
        q,
    ):
        now = clock or datetime.now().astimezone()
        date = (f"Hoje é {_WEEKDAYS[now.weekday()]}, {now.day} de "
                f"{_MONTHS[now.month - 1]} de {now.year}")
        tz = now.strftime("%z")
        if tz:
            date += f" (horário local do computador, UTC{tz[:3]}:{tz[3:]})."
        else:
            date += " (data local do computador)."
        return _result(date, "local_current_date")
    if re.search(r"\b(?:qual|que)\b", q) and re.search(
        r"\b(?:modelo|ia|inteligencia artificial)\b", q
    ) and re.search(r"\b(?:usando|utilizando|usa|utiliza|rodando|executando)\b", q):
        name = str(model_name or "não informado pelo runtime")[:120]
        label = "disponível" if runtime_ready else "não confirmado como pronto"
        return _result(
            f"Sou a Luna, interface do projeto Brain-SSD. "
            f"O modelo de linguagem configurado é {name} "
            f"(estado do runtime: {label}). "
            "Brain-SSD é o projeto, não o nome do modelo de IA.",
            "local_model_identity",
        )
    if re.fullmatch(r"(?:como (?:voce|vc) (?:esta|vai)(?: hoje)?(?: luna)?|"
                    r"tudo bem com (?:voce|vc)(?: luna)?|"
                    r"como (?:esta|vai) (?:a )?luna(?: hoje)?)", q):
        return _result(
            ("Estou funcionando e pronta para conversar." if runtime_ready
             else "Estou aqui, mas o modelo local ainda não está pronto.") +
            " Posso ajudar com o projeto Brain-SSD e com as ferramentas autorizadas.",
            "local_assistant_status",
        )
    if is_first_question_intent(question):
        if not first_question:
            return _result(
                "Não consegui verificar a primeira pergunta desta conversa "
                "no histórico salvo. Não vou adivinhar a partir das últimas mensagens.",
                "local_first_question_unavailable",
            )
        return _result(
            f'A primeira pergunta registrada nesta conversa foi: "{first_question[:500]}".',
            "local_first_question",
        )
    if (re.search(r"\b(?:ultim[ao]s?|recentes?)\b", q) and
            re.search(r"\b(?:cinco|5)\b", q) and
            re.search(r"\b(?:mensagens?|falas?)\b", q) and
            re.search(r"\b(?:resuma|resumir|resume|liste|listar|mostre|mostrar)\b", q)):
        valid = [
            (str(entry["role"]), str(entry["content"]))
            for entry in raw_history if isinstance(entry, dict)
            and entry.get("role") in ("user", "assistant")
            and isinstance(entry.get("content"), str) and entry["content"].strip()
        ] if isinstance(raw_history, list) else []
        if not valid:
            return _result("Não recebi mensagens anteriores para resumir nesta conversa.",
                           "local_recent_messages_unavailable")
        selected = valid[-5:]
        lines = [f"Últimas {len(selected)} mensagens disponíveis nesta conversa "
                 "(trechos, da mais antiga para a mais recente):"]
        for i, (role, message) in enumerate(selected, 1):
            content = " ".join(message.split())
            lines.append(f"{i}. {'Você' if role == 'user' else 'Luna'}: "
                         + content[:170] + ("…" if len(content) > 170 else ""))
        lines.append("Este extrato utiliza o histórico registrado, não lembranças inventadas.")
        return _result("\n".join(lines), "local_recent_messages")
    if re.fullmatch(
        r"(?:voce (?:consegue|pode|sabe) (?:lembrar|se lembrar|recordar) "
        r"(?:do que|de que|o que) (?:conversamos|falamos) (?:anteriormente|antes)|"
        r"voce lembra (?:do que|de que|o que) (?:conversamos|falamos) (?:antes|anteriormente))",
        q,
    ):
        n = len(raw_history) if isinstance(raw_history, list) else 0
        return _result(
            f"Recebi {n} mensagens recentes desta conversa como contexto. "
            "O histórico pode ficar salvo no SQLite local e ser reaberto. "
            "Isso é diferente das lembranças episódicas, que só são guardadas "
            "quando você pede. Não tenho acesso automático a todas as conversas anteriores.",
            "local_history_capability",
        )
    return None
