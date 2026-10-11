"""Strict, opt-in local chat actions; never pretend that Qwen performed them.

Only deliberate command wording triggers a SQLite write. Ordinary conversation
continues through real llama.cpp, and viewing a status does not create memory.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any
from pathlib import Path

from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.history import default_history_path
from brain_ssd.chat.diagnostics import default_diagnostics_dir


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
    # Do not interpret statements ABOUT an assistant's name as a
    # new assignment; only anchored, imperative wording may save it.
    normalized = plain(text)
    if "seu nome padrao" in normalized:
        text = re.sub(r"(?i)padr[aã]o", "padrao", text)
    patterns = (
        # "O seu nome padrão agora é Luna" is an explicit instruction:
        # ordinary Qwen replies must NOT claim a name has been saved.
        r"(?:o\s+)?seu\s+nome\s+(?:padrao\s+)?"
        r"(?:(?:agora|a\s+partir\s+de\s+(?:agora|hoje))\s+)?"
        r"(?:[eé]|vai\s+ser|ser[aá]|fica)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ -]{0,39})",
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
        "Meu nome é ",
        "Luna é o nome que você escolheu",
        "Para ver o histórico de conversas",
        "Os diagnósticos locais ficam",
        "O Brain-SSD não treina os pesos",
        "Esta instalação do Brain-SSD não tem uma integração",
        "A pesquisa web está disponível pelo provedor",
        "A pesquisa web está desativada nesta sessão",
        "Uma fonte pode estar errada",
        "Não posso afirmar como fato algo sobre você",
        "Você disse nesta conversa que seu animal favorito",
        "Não recebi confirmação de que os diagnósticos",
        "Diagnósticos configurados, mas o arquivo",
        "Arquivo de eventos encontrado",
        "Lembrança salva no SQLite local:",
        "Salvei na memória local:",
        "Últimas lembranças salvas explicitamente:",
        "Não há lembranças explícitas salvas no SQLite local.",
        "A memória episódica está ",
        "Não salvei nada. A memória episódica",
        "Olá! Eu sou ",
        "O responsável pelo projeto Brain-SSD é ",
    ))


def local_command(question: str, store: EpisodicMemory | None,
                  *, learned_store: Any = None, web_knowledge: Any = None,
                  web_provider: str | None = None,
                  diagnostics_file: Path | None = None) -> dict[str, Any] | None:
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
            f"Meu nome é {name}." if name
            else "Meu nome é Brain-SSD. Nenhum apelido foi salvo na memória local."
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
            "'/estudar astronomia' pesquisa e guarda diretamente as fontes "
            "públicas sem depender da resposta do Qwen, com as duas permissões. "
            "Marque 'Aprender com as fontes' para guardar trechos e URLs. "
            "'/conhecimento' lista fontes guardadas e "
            "'/esquecer-pesquisa [tópico]' apaga fontes pesquisadas. "
            "Exemplos e pesquisas são guardados localmente quando você pede "
            "e não alteram os pesos do Qwen. "
            "A base de conhecimento SSD atualmente contém documentação de Python e SQLite; "
            "consulta a essa base não significa navegação na internet. "
            "Não executo programas do PC nem acesso seus arquivos pessoais automaticamente."
        )
    elif simple in ("quem criou brain-ssd", "qual e o nome do seu criador") or (
        re.search(r"\b(brain[- ]?ssd|seu projeto)\b", simple)
        and re.search(r"\b(criou|criador|desenvolveu|desenvolvedor|autoria)\b", simple)
    ):
        action = "project_attribution"
        answer = (
            "O responsável pelo projeto Brain-SSD é Hélio Conde "
            "(@HelioConde), proprietário do repositório GitHub "
            "HelioConde/I.A. O modelo Qwen3 é desenvolvido "
            "pela equipe Qwen, e o llama.cpp é um projeto independente."
        )
    elif simple == "quem e luna" and store is not None and plain(store.get_assistant_name() or "") == "luna":
        action = "assistant_name"
        answer = "Luna é o nome que você escolheu para mim. Ele está salvo na memória local."
    elif simple == "quem e luna":
        action = "identity_clarification"
        answer = (
            "Existem várias pessoas e personagens chamados Luna. "
            "Você está falando do nome que quer dar a mim ou de outra Luna?"
        )
    elif simple in ("/nome",):
        action = "assistant_name"
        name = store.get_assistant_name() if store else None
        answer = (
            f"Meu nome é {name}." if name
            else "Meu nome é Brain-SSD. Ainda não há apelido salvo."
        )
    elif simple in (
        "/memorias", "/memoria", "liste minhas memorias", "mostre minhas memorias",
        "quais memorias voce salvou", "quais informacoes voce guardou na memoria",
        "o que voce tem salvo na memoria", "quais informacoes voce tem na memoria",
        "quais informacoes voce possui na memoria", "o que voce lembra de mim",
        "o que voce tem na memoria",
    ) or bool(re.fullmatch(
        r"(?:quais|que) informacoes voce (?:realmente )?"
        r"(?:tem|possui|guardou|salvou) (?:salvas? )?"
        r"(?:na|em) (?:sua )?memoria", simple
    )):
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
        if learned_store is not None or web_knowledge is not None:
            examples = len(learned_store.list(limit=20)) if learned_store else 0
            sources = web_knowledge.count() if web_knowledge else 0
            answer += (
                f"\nExemplos ensinados: {examples} entre os até 20 mais recentes "
                f"(/aprendizados). Fontes pesquisadas: {sources} (/conhecimento). "
                "O histórico de chats fica separado, na barra lateral Conversas. "
                "Fontes públicas armazenadas não são necessariamente corretas."
            )
    elif simple in (
        "como acesso seu historico", "como acesso o seu historico",
        "onde vejo meu historico", "como vejo as conversas anteriores",
        "como acesso o historico", "onde fica o historico",
    ):
        action = "history_access"
        answer = (
            "Para ver o histórico de conversas, abra a barra lateral 'Conversas' "
            "do chat e selecione uma conversa anterior. Mesmo ao iniciar um "
            "novo chat, as anteriores continuam disponíveis nessa lista. "
            "O arquivo SQLite privado fica em "
            f"{default_history_path()}. Histórico não é memória episódica."
        )
    elif simple in (
        "como acesso o log", "como acesso seu log", "onde vejo os logs",
        "onde fica o log", "como acesso os logs", "como vejo os logs",
        "como consigo acessar seus logs", "como consigo acessar os seus logs",
        "como acesso seus logs", "como esta seu log", "como esta o seu log",
        "como estao seus logs", "como estao os seus logs",
    ):
        action = "diagnostics_access"
        path = Path(diagnostics_file) if diagnostics_file is not None else default_diagnostics_dir() / "events.jsonl"
        if diagnostics_file is None:
            state = "Não recebi confirmação de que os diagnósticos estejam habilitados nesta sessão."
        elif not path.is_file():
            state = "Diagnósticos configurados, mas o arquivo de eventos ainda não foi encontrado."
        else:
            try:
                size = path.stat().st_size
                state = f"Arquivo de eventos encontrado ({size} bytes); isso não confirma que não existem erros."
            except OSError:
                state = "Arquivo configurado, mas não consegui verificar os metadados."
        answer = (
            f"{state} O caminho de diagnóstico é {path}. "
            "Para analisar erros, examine os eventos ou consulte o terminal; "
            "não vou afirmar que tudo está funcionando sem essa análise. "
            "Os eventos estruturados não registram o texto das perguntas."
        )
    elif bool(re.fullmatch(
        r"(?:voce |a luna |o brain[- ]?ssd )?(?:consegue |pode |tem como )?"
        r"(?:acessar|ver|ler|consultar|alterar|mexer) "
        r"(?:o |os |a )?(?:meu|minha|meus|minhas) (?:github|repositorios? do github|repositorios?)", simple
    )) or simple in ("voce consegue acessar meu github", "voce tem acesso ao meu github"):
        action = "github_access"
        answer = (
            "Esta instalação do Brain-SSD não tem uma integração autenticada com "
            "sua conta do GitHub. Não consigo listar repositórios privados, "
            "ler seus arquivos pessoais ou fazer alterações por conta própria. "
            "A pesquisa web pública (quando autorizada) não concede acesso à "
            "conta nem permissões de escrita. Para isso é necessário configurar "
            "uma integração autenticada com permissões específicas."
        )
    elif simple in (
        "voce tem acesso a internet", "voce consegue acessar a internet",
        "voce acessa internet", "voce consegue pesquisar na internet",
        "voce pode pesquisar na web", "voce consulta paginas da internet",
    ):
        action = "web_capabilities"
        answer = (
            f"A pesquisa web está disponível pelo provedor {web_provider}. "
            "Ela é usada somente com sua autorização para a pergunta específica. "
            "O Qwen gera respostas localmente; os resultados da internet são "
            "fontes externas e podem conter erros."
            if web_provider else
            "A pesquisa web está desativada nesta sessão. "
            "O Qwen continua respondendo localmente sem acessar sites."
        )
    elif ("pagina da internet" in simple or "fonte da internet" in simple) and (
        "errada" in simple or "falsa" in simple or "incorreta" in simple
    ) and ("como" in simple or "deve" in simple):
        action = "source_reliability"
        answer = (
            "Uma fonte pode estar errada. Devo conferir a data e a origem, "
            "comparar com outras fontes confiáveis quando possível e "
            "deixar clara qualquer incerteza. Guardar um trecho no SSD não "
            "garante que seja verdadeiro. Sem pesquisa autorizada não posso "
            "afirmar que confirmei a informação na internet."
        )
    elif simple in (
        "conte um fato sobre mim que voce nao sabe",
        "diga um fato sobre mim que voce nao sabe",
    ):
        action = "unknown_user_fact"
        answer = (
            "Não posso afirmar como fato algo sobre você que desconheço. "
            "Posso mencionar exemplos de informações que talvez eu não saiba, "
            "mas isso não significa que sejam verdadeiras."
        )
    elif simple in (
        "o que voce aprendeu sozinho ate esse momento",
        "o que voce aprendeu sozinho", "o que voce aprendeu sozinho ate agora",
        "o que voce aprendeu sozinha ate agora",
        "o que voce aprendeu sozinha ate esse momento",
        "o que voce aprendeu sozinha",
        "o que voce aprendeu ate agora",
        "o que voce aprendeu ate esse momento",
    ):
        action = "learning_overview"
        learned_count = len(learned_store.list(limit=20)) if learned_store else 0
        research_count = web_knowledge.count() if web_knowledge else 0
        answer = (
            "O Brain-SSD não treina os pesos do Qwen nem aprende fatos sozinho "
            "a partir de qualquer conversa. "
            f"Há {learned_count} exemplo(s) explícito(s) entre os até 20 mais recentes "
            f"e {research_count} fonte(s) pública(s) no banco de pesquisas. "
            "Essas fontes podem estar desatualizadas e não são fatos confirmados. "
            "Use /aprendizados, /conhecimento e /memorias para conferir os registros."
        )
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


def conversation_followup(question: str, history: list[dict[str, str]]) -> dict[str, Any] | None:
    """Answer a narrow factual follow-up from THIS conversation, not SQLite.

    Do not infer reasons for stated preferences. Never write the information
    to permanent episodic memory without an explicit save request.
    """
    if not isinstance(question, str) or not isinstance(history, list):
        return None
    normalized = re.sub(r"[?.!]+$", "", plain(question)).strip()
    if not re.fullmatch(
        r"(?:por que |porque )?(?:voce |vc )?(?:acha |pensa )?"
        r"(?:que )?(?:eu )?gosto (?:desse|deste|de tal|daquele) animal"
        r"|(?:por que|porque) (?:voce )?acha que (?:eu )?gosto "
        r"(?:desse|deste|daquele) animal",
        normalized,
    ):
        return None
    for item in reversed(history):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        content = item.get("content")
        if not isinstance(content, str):
            continue
        source = plain(content)
        fact = re.search(
            r"\b(?:o )?meu animal favorito (?:e|eh) "
            r"(?:(?:o|a|um|uma) )?([a-z-]{2,35})\b",
            source,
        )
        if fact:
            animal = fact.group(1)
            answer = (
                f"Você disse nesta conversa que seu animal favorito é {animal}, "
                "mas não explicou por que gosta dele. Eu não tenho como saber "
                "o motivo sem você contar; qualquer explicação seria hipótese."
            )
            return {
                "answer": answer, "mode": "local_command",
                "local_action": "conversation_context",
                "source": "current_chat_history",
                "metrics": {}, "active_pages": 0, "sources_from_ssd": 0,
                "episodic_memories_used": 0,
                "episodic_ambiguities_detected": 0,
                "episodic_ambiguities_withheld": False,
                "cognitive_shadow": None,
            }
    return None
