"""Strict, opt-in local chat actions; never pretend that Qwen performed them.

Only deliberate command wording triggers a SQLite write. Ordinary conversation
continues through real llama.cpp, and viewing a status does not create memory.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from brain_ssd.chat.episodic import EpisodicMemory


def plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def _parse_save_request(message: str) -> str | None:
    # Require an explicit command, not a casual mention of a fact or preference.
    match = re.fullmatch(
        r"\s*(?:salve|salvar|guarde|guardar|memorize|memorizar)"
        r"\s+(?:(?:isso|esta informação)\s+)?"
        r"(?:na\s+mem[oó]ria|em\s+mem[oó]ria|uma\s+lembran[cç]a)"
        r"\s*(?:[:,]?\s*(?:que\s+)?)"
        r"(.{1,500}?)\s*[.!]?\s*",
        message, re.IGNORECASE,
    )
    if match:
        return match.group(1).strip().rstrip(".!")
    match = re.fullmatch(
        r"\s*lembre-se\s+de\s+que\s+(.{1,500}?)\s*[.!]?\s*",
        message, re.IGNORECASE,
    )
    return match.group(1).strip().rstrip(".!") if match else None


def _name_from_memory_request(note: str) -> str | None:
    # Match precisely assistant nickname, not "meu nome" (the user's identity).
    match = re.fullmatch(
        r"(?:o\s+)?(?:seu|teu|da\s+assistente|do\s+assistente)\s+nome"
        r"\s+(?:[eé]|ser[aá])\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ -]{0,39})",
        note, flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _direct_assistant_name_request(message: str) -> str | None:
    """Detect *deliberate* nickname changes, never infer from a question.

    'Seu nome a partir de hoje é Luna' is an explicit instruction. A sentence
    that merely discusses the assistant's name is not consent to save memory.
    """
    text = message.strip()
    if not text or text.endswith("?"):
        return None
    patterns = (
        r"(?:a\s+partir\s+de\s+hoje[,]?\s+(?:o\s+)?seu\s+nome"
        r"|(?:o\s+)?seu\s+nome\s+a\s+partir\s+de\s+hoje)"
        r"\s+(?:[eé]|ser[aá]|vai\s+ser)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ -]{0,39})",
        r"(?:o\s+)?seu\s+nome\s+(?:[eé]|ser[aá])\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ -]{0,39})",
        r"(?:quero\s+te\s+chamar\s+de|vou\s+te\s+chamar\s+de"
        r"|pode\s+se\s+chamar|te\s+chamarei\s+de)"
        r"\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ -]{0,39})",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern + r"\s*[.!]?", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def is_local_action_answer(answer: str) -> bool:
    """Recognize previously stored deterministic replies for prompt hygiene.

    History stays on disk and visible to the user. Only Qwen prompt context
    discards these Python/SQLite outputs to avoid repeated canned responses.
    """
    return answer.startswith((
        "Sou o Brain-SSD, uma IA local experimental. Posso conversar, explicar ",
        "Meu nome é Brain-SSD. Ainda não há apelido salvo.",
        "Meu nome padrão é Brain-SSD. Nenhum apelido",
        "Meu nome escolhido é ",
        "Lembrança salva no SQLite local:",
        "Salvei na memória local:",
        "Últimas lembranças salvas explicitamente:",
        "Não há lembranças explícitas salvas no SQLite local.",
        "A memória episódica está ",
        "Não salvei nada. A memória episódica",
        "Olá! Eu sou ",
        "O responsável pelo projeto Brain-SSD é ",
    ))


def local_command(question: str, store: EpisodicMemory | None) -> dict[str, Any] | None:
    """Return a truthful app action; None means let the real Qwen answer."""
    simple = re.sub(r"[?.!]+\s*$", "", plain(question)).strip()
    greeting_text = simple
    simple = re.sub(r"^(?:oi|ola|bom dia|boa tarde|boa noite)[,\s]+", "", simple)
    save = _parse_save_request(question)
    direct_name = _direct_assistant_name_request(question) if save is None else None
    answer: str | None = None
    action: str | None = None
    if save is not None or direct_name is not None:
        action = "memory_save"
        if store is None:
            answer = (
                "Não salvei nada. A memória episódica está desativada. "
                "Abra o chat com --episodic-memory ou pelo iniciador COM MEMÓRIA."
            )
        else:
            name = _name_from_memory_request(save) if save is not None else direct_name
            if name is not None:
                saved = store.remember_assistant_name(name)
                answer = (
                    f"Salvei na memória local: {saved['content']}. "
                    "Continuará disponível em novas conversas e após reiniciar o programa."
                )
            else:
                saved = store.add(save)  # Non-nickname explicit note.
                answer = (
                    f"Lembrança salva no SQLite local: {saved['content']}. "
                    "Você pode revisar, editar ou apagar em Memórias."
                )
    elif greeting_text in ("oi", "ola", "bom dia", "boa tarde", "boa noite") or (
        store is not None
        and greeting_text.startswith(("oi ", "ola ", "bom dia ", "boa tarde ", "boa noite "))
        and (saved_name := plain(store.get_assistant_name() or "")) != ""
        and greeting_text in tuple(f"{g} {saved_name}" for g in
                            ("oi", "ola", "bom dia", "boa tarde", "boa noite"))
    ):
        action = "greeting"
        chosen = (store.get_assistant_name() if store else None) or "Brain-SSD"
        answer = f"Olá! Eu sou {chosen}. Em que posso ajudar?"
    elif simple in (
        "qual seu nome", "qual e seu nome", "como voce se chama",
        "qual o seu nome", "qual e o seu nome", "quem e voce",
        "qual nome voce recebeu", "qual nome eu te dei",
    ):
        action = "assistant_name"
        name = store.get_assistant_name() if store else None
        answer = (
            f"Meu nome escolhido é {name}. Ele está salvo na memória local."
            if name else "Meu nome padrão é Brain-SSD. Nenhum apelido foi salvo na memória local."
        )
    elif simple in (
        "quais comandos voce tem", "qual comandos voce tem", "qual comandos tem",
        "quais comandos tem", "que comandos voce tem",
        "quais informacoes voce sabe sobre voce", "quais informacoes voce sabe sobre si",
        "quais sao seus comandos", "o que voce consegue fazer", "o que voce pode fazer",
        "/ajuda", "/help", "ajuda comandos",
    ):
        action = "help"
        answer = (
            "Sou o Brain-SSD, uma IA local experimental. Posso conversar, explicar "
            "conceitos e ajudar com textos e código (o modelo local pode errar). "
            "Comandos locais reais: 'salve na memória que ...' (guarda uma nota somente "
            "quando você pedir), '/memorias' (lista notas salvas), '/nome' (mostra meu nome) "
            "e '/ajuda' (mostra estes comandos). "
            "Para ensinar uma resposta: '/ensinar Olá => Olá!'; "
            "para revisar: '/aprendizados'; para apagar: '/desaprender Olá'. "
            "Pesquisa: '/pesquisar astronomia' com autorização no navegador; "
            "marque 'Aprender com as fontes' para guardar os trechos públicos "
            "e suas URLs. '/conhecimento' lista fontes guardadas e "
            "'/esquecer-pesquisa [tópico]' apaga fontes pesquisadas. "
            "Exemplos e pesquisas são guardados localmente quando você pede "
            "e não alteram os pesos do Qwen. "
            "A base de conhecimento SSD atualmente contém documentação de Python e SQLite; "
            "consulta a essa base não significa navegação na internet. "
            "Não executo programas do PC nem acesso seus arquivos pessoais automaticamente."
        )
    elif simple in ("quem criou brain-ssd", "qual e o nome do seu criador"):
        action = "project_attribution"
        answer = (
            "O responsável pelo projeto Brain-SSD é Hélio Conde "
            "(@HelioConde), proprietário do repositório GitHub "
            "HelioConde/I.A. O modelo Qwen3 é desenvolvido "
            "pela equipe Qwen, e o llama.cpp é um projeto independente."
        )
    elif simple in ("/nome",):
        action = "assistant_name"
        name = store.get_assistant_name() if store else None
        answer = (
            f"Meu nome escolhido é {name}. Esse nome está salvo em SQLite local."
            if name else "Meu nome é Brain-SSD. Ainda não há apelido salvo."
        )
    elif simple in (
        "/memorias", "/memoria", "liste minhas memorias", "mostre minhas memorias",
        "quais memorias voce salvou", "quais informacoes voce guardou na memoria",
        "o que voce tem salvo na memoria",
    ):
        action = "memory_list"
        if store is None:
            answer = "A memória episódica está desativada nesta sessão; nenhuma nota foi lida."
        else:
            memories = store.list(limit=10)
            if memories:
                lines = [f"{i}. {item['content']}" for i, item in enumerate(memories, 1)]
                answer = "Últimas lembranças salvas explicitamente:\n" + "\n".join(lines)
                if len(memories) == 10:
                    answer += "\nExibindo no máximo as 10 mais recentes; use o painel Memórias para consultar as demais."
            else:
                answer = "Não há lembranças explícitas salvas no SQLite local."
    elif simple in (
        "voce ainda nao salvou informacoes na memoria",
        "voce ainda nao salvar informacoes na memoria",
        "como esta sua memoria", "como esta a sua memoria",
        "sua memoria esta funcionando", "a memoria esta funcionando",
    ):
        action = "memory_status"
        if store is None:
            answer = "A memória episódica está desativada nesta sessão. Nenhuma lembrança é gravada automaticamente."
        else:
            count = len(store.list(limit=100))
            answer = (
                f"A memória episódica está ativada e há {count}"
                + (" ou mais" if count == 100 else "")
                + " nota(s) entre as mais recentes no SQLite local. "
                "As notas são salvas somente com pedidos explícitos; "
                "histórico de conversa e memória são coisas diferentes. "
                "Use /memorias para ver as últimas notas."
            )
    if answer is None:
        return None
    return {
        "answer": answer,
        "mode": "local_command",
        "local_action": action,
        "source": "local_python_action",
        "metrics": {},
        "active_pages": 0,
        "sources_from_ssd": 0,
        "episodic_memories_used": 0,
        "episodic_ambiguities_detected": 0,
        "episodic_ambiguities_withheld": False,
        "cognitive_shadow": None,
        "note": "Operação local do aplicativo: não houve geração do Qwen nesta resposta.",
    }
