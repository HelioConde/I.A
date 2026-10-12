"""Deterministic, truthful Copilot routes for explicit Windows questions.

The Qwen text-only model never receives pixels and cannot invent monitor
contents. The image, if any, is returned for local UI preview only.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from brain_ssd.chat.copilot import CopilotPermissionError, LocalCopilot


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return " ".join(normalized.split())


def _result(answer: str, action: str, image_data_url: str | None = None,
            extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "answer": answer,
        "mode": "local_command",
        "local_action": action,
        "source": "windows_local_tools",
        "metrics": {},
        "active_pages": 0,
        "sources_from_ssd": 0,
        "episodic_memories_used": 0,
        "episodic_ambiguities_detected": 0,
        "episodic_ambiguities_withheld": False,
        "cognitive_shadow": None,
        "note": "Dados lidos por ferramentas locais do Windows; não gerados pelo Qwen.",
    }
    if image_data_url is not None:
        out["copilot_image_data_url"] = image_data_url
    if extra:
        out.update(extra)
    return out


def _is_system_question(text: str) -> bool:
    # Only requests about the *user's own* device, not generic PC advice.
    if not re.search(r"\b(meu computador|meu pc|minha maquina|meu notebook|"
                     r"hardware do meu|especificacoes do meu|configuracao do meu)\b", text):
        return False
    return bool(re.search(r"\b(sabe|mostre|mostrar|diga|informe|qual|quais|"
                          r"verifique|verificar|analise|informacoes|configuracao|"
                          r"hardware|especificacoes|tem|possui|diagnostico)\b", text))


def _screen_request(text: str) -> tuple[bool, int]:
    # Explicit instruction + "tela"/"monitor" is mandatory for a screenshot.
    instruction = re.search(r"\b(olhe|veja|analise|examine|capture|capturar|"
                            r"fotografe|tire uma foto|mostre|identifique|"
                            r"identificar|quais|liste|listar)\b", text)
    target = re.search(r"\b(?:monitor|tela)(?:\s*(?:numero|n|no|nº|#))?"
                       r"\s*(\d{1,2})?\b", text)
    if not (instruction and target):
        return False, 1
    number = int(target.group(1)) if target.group(1) else 1
    return True, number


def _is_window_request(text: str) -> bool:
    return bool(re.search(r"\b(programas? abert|aplicativos? abert|janelas? abert|"
                          r"apps? abert|programas? em execucao|"
                          r"quais programas?|quais aplicativos?|"
                          r"identifique os programas|liste os programas)\b", text))


_APP_NAMES = {
    "godot": "godot", "visual studio code": "visual studio code", "vs code": "code",
    "vscode": "code", "chrome": "chrome", "steam": "steam",
    "python": "python", "bloco de notas": "notepad", "notepad": "notepad",
    "calculadora": "calc", "calculator": "calc",
}


def _app_name(text: str) -> str | None:
    for alias in sorted(_APP_NAMES, key=len, reverse=True):
        if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text):
            return _APP_NAMES[alias]
    return None


def _inventory_intent(text: str) -> str | None:
    if re.search(r"\b(instalad[oa]s?|instalacao|versao instalada)\b", text):
        return "installed"
    if (re.search(r"\b(programas?|aplicativos?|apps?|processos?|godot|chrome|steam|code|python)\b", text)
            and re.search(r"\b(abert[oa]s?|rodando|executando|execucao|ativos?|segundo plano|"
                          r"consumindo|consome|em primeiro plano|travados?)\b", text)):
        return "running"
    return None


def _app_reply(question: str, copilot: LocalCopilot, intent: str) -> dict[str, Any]:
    query = _app_name(question)
    if not copilot.apps_enabled:
        return _result(
            "A consulta de aplicativos do Windows não foi autorizada nesta sessão. "
            "Reinicie o iniciador do Copiloto e escolha autorizar o inventário, sem conceder acesso a arquivos.",
            "copilot_apps_disabled",
        )
    try:
        data = copilot.installed_apps(query) if intent == "installed" else copilot.running_apps(query)
    except (CopilotPermissionError, OSError):
        return _result("A consulta do Windows falhou; nenhum programa foi confirmado.",
                       "copilot_apps_unavailable")
    rows = data.get("items", [])
    limit_type = "instalados registrados" if intent == "installed" else "processos ativos"
    intro = (f"Consulta local de {limit_type}, fonte: {data.get('source', 'Windows')}.")
    if query:
        intro += f" Filtro: {query}."
    if rows:
        if intent == "installed":
            detail = [
                "• " + r["name"] + (" — versão " + r["version"] if r.get("version") else "")
                for r in rows[:20]
            ]
        else:
            detail = ["• " + r["name"] + " (PID " + str(r["pid"]) + ")" for r in rows[:20]]
    else:
        detail = ["Nenhum registro correspondente foi encontrado; isso não prova que não está instalado ou executando."]
    if data.get("truncated"):
        detail.append("Resultados limitados aos primeiros registros; refine o nome.")
    if intent == "installed":
        detail.append("Aplicativos portáteis e instalações sem registro podem não aparecer. "
                      "Não foi verificado o caminho do executável.")
    else:
        detail.append("Esta lista não representa janelas visíveis e não mede CPU ou RAM em tempo real.")
    if intent == "running" and re.search(r"\b(cpu|ram|memoria|mais|travado|travados|sem responder)\b", question):
        action = "copilot_running_apps_limited"
    else:
        action = "copilot_installed_apps" if intent == "installed" else "copilot_running_apps"
    return _result("\n".join([intro, *detail]), action)


def _launch_intent(question: str) -> tuple[str | None, bool, bool]:
    wants = bool(re.search(r"\b(abra|abre|abrir|inicie|iniciar|inicia|execute|executar)\b", question))
    if not wants:
        return None, False, False
    app = None
    if re.search(r"\b(bloco de notas|notepad)\b", question):
        app = "notepad"
    elif re.search(r"\b(calculadora|calculator)\b", question):
        app = "calculator"
    question_only = bool(re.search(r"\b(consegue|pode|poderia|sabe)\b", question))
    imperative = bool(re.match(r"^(?:por favor,?\s+)?(?:abra|abre|inicie|inicia|execute)\b", question))
    return app, question_only, imperative


def _launch_reply(question: str, copilot: LocalCopilot | None) -> dict[str, Any] | None:
    app, question_only, imperative = _launch_intent(question)
    if app is None and not (question_only or imperative):
        return None
    if app is None:
        return _result(
            "Esta versão não abre o aplicativo solicitado. A abertura segura está limitada "
            "a Bloco de Notas e Calculadora, com autorização da sessão e confirmação por clique.",
            "copilot_launch_unsupported",
        )
    if copilot is None or not copilot.launch_enabled:
        return _result(
            "Posso preparar a abertura de Bloco de Notas ou Calculadora, mas o controle "
            "de aplicativos está desativado. Reinicie o Copiloto e autorize esta função; "
            "nada foi aberto.",
            "copilot_launch_disabled",
        )
    if question_only or not imperative:
        return _result(
            "Posso preparar a abertura do aplicativo, mas nunca executá-la só porque "
            "a IA respondeu. Diga 'Abra o Bloco de Notas' ou 'Abra a Calculadora' "
            "e confirme no botão da conversa.",
            "copilot_launch_info",
        )
    try:
        offer = copilot.offer_launch(app)
    except (CopilotPermissionError, OSError):
        return _result("Não foi possível preparar a abertura. Nenhuma aplicação foi iniciada.",
                       "copilot_launch_unavailable")
    return _result(
        "Pedido de abertura de " + offer["label"] + " preparado. "
        "Nenhuma aplicação foi iniciada. Clique em 'Confirmar abertura' nesta "
        "mensagem para executar apenas este pedido. O pedido expira em 90 segundos.",
        "copilot_launch_proposal",
        extra={"copilot_launch_token": offer["token"],
               "copilot_launch_app": offer["app_id"],
               "copilot_launch_label": offer["label"]},
    )


def _grounded_desktop_question(question: str, copilot: LocalCopilot | None) -> dict[str, Any] | None:
    """Resolve desktop capability claims before loose hardware/LLM routing.

    Only explicitly requested reads happen; other questions explain limitations.
    Paths and image files are checked using the existing authorized-root gates.
    """
    simple = _plain(question)
    # A user asking about their OWN tabs must not fall through to Qwen or
    # be answered from tasklist.exe. Browser processes != open tab URLs.
    personal_tabs = bool(
        re.search(r"\b(?:abas?|guias?)\b", simple)
        and (
            re.search(r"\b(?:minhas?|meus|tenho|estou|quais?|liste|listar|mostre|verifique|consegue|"
                      r"abert[ao]s?|mandou|enviou)\b", simple)
            or re.search(r"\b(?:isso|nao e|nao sao)\b.*\b(?:abas?|guias?)\b", simple)
        )
    )
    if personal_tabs:
        return _result(
            "Você tem razão: a lista de chrome.exe/PID mostra PROCESSOS do Windows, "
            "não as abas abertas no Chrome. Eu não consultei as URLs nem os títulos "
            "das suas abas e não consigo enumerá-las nesta versão. "
            "Se quiser trabalhar com uma aba, cole o link ou copie o texto dela. "
            "A captura autorizada mostra a tela, mas não revela automaticamente "
            "a lista completa de abas.",
            "copilot_browser_tabs_unsupported",
        )
    # Voice transcription can refer vaguely to what is 'open in Chrome'.
    # Clarify rather than silently substituting a process list for tabs.
    if (re.search(r"\b(?:chrome|google chrome|edge)\b", simple)
            and re.search(r"\b(?:quais?|verifique|mostre|abert[ao]s?)\b", simple)
            and not re.search(r"\b(?:processos?|pids?|programas?|aplicativos?|janelas?|abas?|guias?)\b", simple)):
        return _result(
            "Você quer verificar as ABAS do navegador ou os PROCESSOS do Chrome? "
            "Consigo consultar processos, mas ainda não consigo ler a lista de abas. "
            "Nenhuma aba foi consultada.",
            "copilot_browser_intent_clarification",
        )
    if (re.search(r"\b(?:abas?|guias?)\b", simple)
            and re.search(r"\b(?:navegador|chrome|edge|browser)\b", simple)
            and re.search(r"\b(?:quais|abert[ao]s?|estou|tenho|minhas|meus|liste|mostre)\b", simple)):
        return _result(
            "Ainda não consigo enumerar as abas abertas do Chrome ou Edge. "
            "A consulta de processos do Windows não identifica as URLs das abas. "
            "Não acessei o navegador. Para mostrar uma aba, copie o endereço "
            "ou peça uma captura explícita do monitor; o Qwen atual não interpreta pixels.",
            "copilot_browser_tabs_unsupported",
        )
    if re.search(r"\b(?:funcoes|funcionalidades|capacidades|recursos)\b", simple) and re.search(
        r"\b(?:meu pc|meu computador|no pc|no computador|voce consegue|voce pode)\b", simple
    ):
        if copilot is None:
            return _result(
                "O Copiloto não está ativo. Posso conversar com o Qwen local, "
                "mas não tenho acesso automático ao PC; inicie o Copiloto para habilitar ferramentas.",
                "copilot_capabilities_disabled",
            )
        features = copilot.status()
        return _result(
            "Funções verificadas nesta sessão da Luna:\n"
            + "• Leitura de pastas e arquivos: " + ("autorizada" if features.get("files_enabled") else "desativada") + "\n"
            + "• Captura de tela solicitada: " + ("autorizada" if features.get("screen_enabled") else "desativada") + "\n"
            + "• Inventário de aplicativos: " + ("autorizado" if features.get("apps_enabled") else "desativado") + "\n"
            + "• Abertura de Bloco de Notas/Calculadora: " + ("com confirmação" if features.get("launch_enabled") else "desativada") + "\n"
            + "• Edição de CÓDIGO: " + ("diff, backup e confirmação" if features.get("edit_enabled") else "desativada") + "\n"
            + "Não navego nas abas do navegador, não interpreto imagens com este Qwen "
            "e não crio arquivos de texto arbitrários nesta versão. "
            "Autorizar uma raiz não concede automaticamente permissão de escrita.",
            "copilot_capabilities",
        )
    if re.search(r"\b(?:pastas|diretorios)\b", simple) and re.search(
        r"\b(?:principais|raiz|meu pc|meu computador|do pc|disco|unidade c)\b", simple
    ):
        if copilot is None or not copilot.status().get("files_enabled"):
            return _result("Não há uma pasta autorizada para listar. "
                           "Configure a raiz no LUNA.ini; não vou inventar diretórios.",
                           "copilot_folders_disabled")
        root = next(iter(getattr(copilot, "roots", ())), None)
        if root is None:
            return _result("Não existe raiz autorizada para consultar.",
                           "copilot_folders_disabled")
        try:
            directory = copilot.list_directory(str(root))
        except (CopilotPermissionError, OSError, ValueError):
            return _result("Não foi possível listar a pasta autorizada.",
                           "copilot_folders_unavailable")
        names = [item["name"] for item in directory.get("entries", [])
                 if item.get("type") == "folder"][:25]
        lines = ["Pastas conferidas agora em " + str(directory["path"]) + ":"]
        lines.extend("• " + item for item in names)
        if not names:
            lines.append("Nenhuma subpasta visível foi encontrada nos limites desta consulta.")
        if directory.get("truncated"):
            lines.append("A consulta é limitada; outras pastas podem não aparecer.")
        return _result("\n".join(lines), "copilot_folders")
    if re.search(r"\b(?:jogos?)\b", simple) and re.search(
        r"\b(?:instalado|instalados|instalada|instaladas|tenho no|tenho instal)\b", simple
    ):
        return _result(
            "O inventário do Windows lista aplicativos registrados, mas não classifica "
            "com segurança quais são jogos. Não posso apresentar essa lista como "
            "uma lista completa de jogos instalados. Posso consultar um título "
            "específico ou listar aplicativos registrados sem essa classificação.",
            "copilot_games_registry_limited",
        )
    if re.search(r"\b(?:o que (?:voce )?esta vendo|o que aparece|o que (?:voce )?ve)\b", simple) and re.search(
        r"\b(?:minha tela|meu monitor|na tela|no monitor)\b", simple
    ):
        return _result(
            "Ainda não capturei sua tela nesta pergunta. Posso mostrar uma captura "
            "do monitor solicitado com sua permissão, mas este Qwen não interpreta pixels. "
            "Diga 'Mostre o monitor 1' ou 'Mostre o monitor 2' para abrir a prévia; "
            "para obter texto, solicite OCR local.",
            "copilot_screen_not_observed",
        )
    if re.search(r"\b(?:voce consegue|consegue|pode|sabe)\b.*\b(?:ver|visualizar|enxergar)\b.*\b(?:monitor|tela|imagem|imagen|imagens)\b", simple):
        return _result(
            "Posso capturar um monitor explicitamente solicitado, quando autorizado, "
            "e exibir a captura no chat. Mas o Qwen instalado é apenas texto: "
            "não interpreta pixels nem consegue dizer o que aparece na imagem. "
            "Para uma captura, diga 'Mostre o monitor 1' ou 'Mostre o monitor 2'. "
            "Para texto visível, peça OCR local, que pode errar.",
            "copilot_vision_limitation",
        )
    if re.search(r"\b(?:voce consegue|consegue|pode|sabe)\b.*\b(?:visualizar|analisar|interpretar)\b.*\b(?:imagem|imagen|imagens|foto|fotos)\b", simple):
        return _result(
            "Consigo exibir uma prévia de imagem autorizada, mas este Qwen é somente texto "
            "e não a compreende visualmente. Para texto legível de telas, posso tentar OCR "
            "sob solicitação. Não analisei nenhuma imagem nesta resposta.",
            "copilot_image_limitation",
        )
    if re.search(r"\b(?:crie|criar|cria|grave|salve|escreva|gerar|gere)\b", simple) and re.search(
        r"\b(?:arquivo|texto|txt|documento)\b", simple
    ) and (bool(re.search(r"[a-z]:[/\\\\]", simple))
           or bool(re.search(r"\b(?:arquivo|salve|grave)\b", simple))
           or bool(re.search(r"\b(?:na|no|em|para) (?:pasta|diretorio|disco)\b", simple))
           or "crie o texto" in simple):
        return _result(
            "Posso redigir o conteúdo aqui, mas esta versão do chat não grava arquivos "
            ".txt automaticamente. A permissão atual de edição cobre apenas CÓDIGO "
            "com diff e confirmação. Nenhum arquivo foi criado. "
            "Copie o texto para o Bloco de Notas ou use o editor de código "
            "do Copiloto para arquivos de código autorizados.",
            "copilot_text_write_unsupported",
        )
    if re.search(r"\b(?:imagem|imagen|imagens|fotos?|png|jpg|jpeg|webp)\b", simple) and re.search(
        r"\b(?:downloads?|baixados?)\b", simple
    ) and re.search(r"\b(?:localize|localizar|ache|encontre|mostre|mostrar|liste|listar|primeir[ao])\b", simple):
        if copilot is None or not copilot.status().get("files_enabled"):
            return _result("Downloads não está autorizado. Não pesquisei nem localizei imagens.",
                           "copilot_downloads_disabled")
        downloads = Path.home() / "Downloads"
        try:
            directory = copilot.list_directory(str(downloads))
        except (CopilotPermissionError, ValueError, OSError):
            return _result(
                "Não consegui abrir a pasta Downloads padrão dentro das raízes autorizadas. "
                "Nenhuma imagem foi localizada. Verifique a pasta no Copiloto.",
                "copilot_downloads_unavailable",
            )
        image_names = sorted(
            (item["name"] for item in directory.get("entries", [])
             if item.get("type") == "file"
             and Path(item["name"]).suffix.casefold() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}),
            key=str.casefold,
        )
        if not image_names:
            return _result(
                "Não identifiquei imagens nos primeiros registros autorizados de Downloads. "
                "A busca é limitada a 100 entradas e pode não incluir todos os arquivos.",
                "copilot_downloads_empty",
            )
        if re.search(r"\b(?:mostre|mostrar|exiba|primeir[ao])\b", simple):
            try:
                preview = copilot.preview_image(str(downloads / image_names[0]))
                return _result(
                    "Primeira imagem por ordem alfabética nos registros consultados: "
                    + image_names[0] + ". Exibindo prévia (sem interpretação visual pelo Qwen).",
                    "copilot_image_preview", image_data_url=preview["image_data_url"],
                )
            except (CopilotPermissionError, OSError, ValueError):
                return _result(
                    "Encontrei o arquivo " + image_names[0] +
                    ", mas não consegui gerar a prévia. Nenhuma imagem foi interpretada.",
                    "copilot_image_preview_unavailable",
                )
        return _result(
            "Imagens encontradas nos primeiros registros da pasta Downloads:\n" +
            "\n".join("• " + name for name in image_names[:12]) +
            ("\nListagem parcial: limite de entradas atingido." if directory.get("truncated") else ""),
            "copilot_downloads_list",
        )
    return None


def copilot_answer(question: str, copilot: LocalCopilot | None) -> dict[str, Any] | None:
    """Return a truthful local result only for clearly selected Copilot intents."""
    if not isinstance(question, str):
        return None
    # Agent Core only prepares deterministic read-only workflows here.
    investigate_godot = re.fullmatch(
        r'/investigar-godot\s+"([^"\r\n]+)"\s*::\s*(.+)',
        question.strip(), re.I | re.S)
    investigate_project = re.fullmatch(
        r'/investigar-projeto\s+"([^"\r\n]+)"\s*',
        question.strip(), re.I)
    investigate_code = re.fullmatch(
        r'/investigar-codigo\s+"([^"\r\n]+)"\s*',
        question.strip(), re.I)
    investigate_pc = question.strip().casefold() == "/investigar-pc"
    if (investigate_godot or investigate_project or investigate_code
            or investigate_pc):
        if copilot is None:
            return _result(
                "O Agent Core local não está ativo. Inicie o Copiloto Windows.",
                "copilot_disabled",
            )
        try:
            if investigate_godot:
                plan = copilot.plan_investigation(
                    "godot_diagnosis", project=investigate_godot.group(1),
                    error=investigate_godot.group(2))
            elif investigate_project:
                plan = copilot.plan_investigation(
                    "godot_overview", project=investigate_project.group(1))
            elif investigate_code:
                plan = copilot.plan_investigation(
                    "code_review", path=investigate_code.group(1))
            else:
                plan = copilot.plan_investigation("pc_report")
        except (CopilotPermissionError, OSError, ValueError):
            return _result(
                "Não foi possível preparar a investigação. Confira a pasta "
                "autorizada, o arquivo e as informações fornecidas.",
                "copilot_agent_unavailable",
            )
        steps = "\n".join(
            str(step["number"]) + ". " + step["title"] +
            " [" + step["tool"] + "]" for step in plan["steps"]
        )
        return _result(
            "Plano de investigação local (nenhuma ferramenta executada):\n" +
            steps + "\n" + plan["risk"] +
            "\nClique em 'Investigar agora' para consultar os dados reais. "
            "A autorização expira em 90 segundos.",
            "copilot_agent_plan",
            extra={"copilot_agent_token": plan["token"],
                   "copilot_agent_task": plan["task"]},
        )

    validation_command = re.fullmatch(
        r'/validar-godot\s+"([^"\r\n]+)"\s*::\s*(res://[^\s\r\n]+\.gd)\s*',
        question.strip(), re.I)
    if validation_command:
        if copilot is None or not copilot.status().get("godot_validate_enabled"):
            return _result(
                "Verificação Godot desativada. Reinicie o Copiloto com uma pasta "
                "de projeto e executável Godot escolhido por você, autorizando "
                "cada execução separadamente.",
                "copilot_godot_validation_disabled"
            )
        try:
            offer = copilot.propose_godot_validation(
                validation_command.group(1), validation_command.group(2))
        except (CopilotPermissionError, OSError, ValueError):
            return _result(
                "Não foi possível preparar esta verificação. Confira o script, "
                "a pasta autorizada e o executável Godot.",
                "copilot_godot_validation_unavailable",
            )
        return _result(
            "Verificação de sintaxe proposta (NADA foi executado).\n"
            "Projeto: " + offer["project"] +
            "\nScript: " + offer["script"] +
            "\nGodot: " + offer["binary"] +
            "\nArgumentos: " + " ".join(offer["command_flags"]) +
            "\nAVISO: " + offer["warning"] +
            "\nSe concordar, use o botão de confirmação desta mensagem. "
            "Prazo: 90 segundos; limite da execução: 30 segundos.",
            "copilot_godot_validation_proposal",
            extra={"copilot_godot_validation_token": offer["token"],
                   "copilot_godot_validation_script": offer["script"],
                   "copilot_godot_validation_project": offer["project"]},
        )

    # Bound and ground Godot diagnosis to the files in an authorized project.
    project_command = re.fullmatch(r"/(?:projeto|analisar-projeto)\s+(.+)",
                                    question.strip(), re.I | re.S)
    error_command = re.fullmatch(r'/erro-godot\s+"([^"\r\n]+)"\s*::\s*(.+)',
                                  question.strip(), re.I | re.S)
    if project_command or error_command:
        if copilot is None or not copilot.status().get("files_enabled"):
            return _result("Autorize a pasta do projeto ao iniciar o Copiloto.",
                           "copilot_disabled")
        try:
            if project_command:
                report = copilot.inspect_godot_project(project_command.group(1).strip().strip('"'))
                rows = [
                    "Projeto Godot conferido: " + report["project_root"],
                    f"Scripts: {report['script_count']}; cenas: {report['scene_count']}; recursos: {report['resources_count']}.",
                    *["• " + name for name in report["files"][:12]],
                    *["• TODO/FIXME " + item["file"] + ":" + str(item["line"])
                      for item in report["todo"][:5]],
                ]
                if report["truncated"]:
                    rows.append("A inspeção atingiu um limite de arquivos/profundidade; resultados parciais.")
                rows.append("Não executei Godot, nem alterei o projeto. "
                            "Use /erro-godot \"CAMINHO\" :: TEXTO DO ERRO para analisar uma falha.")
                return _result("\n".join(rows), "copilot_godot_project")
            path, failure = error_command.groups()
            report = copilot.diagnose_godot_error(path, failure.strip())
            rows = ["Diagnóstico baseado no erro fornecido e nos arquivos autorizados."]
            for match in report["matches"][:3]:
                rows.append("• Arquivo: " + match["file"] +
                            (":" + str(match["reported_line"]) if match["reported_line"] else "") +
                            " (" + match["source"] + ")")
                for line in match["snippet"][:7]:
                    rows.append(f"  {line['line']}: {line['text']}")
            rows.extend("• " + item for item in report["recommendations"])
            rows.append("Nenhuma correção foi aplicada. Verifique as evidências antes de editar.")
            return _result("\n".join(rows), "copilot_godot_diagnosis")
        except (CopilotPermissionError, OSError, ValueError):
            return _result("Não foi possível analisar este projeto/erro. "
                           "Confira a pasta autorizada e a mensagem fornecida.",
                           "copilot_godot_unavailable")

    # Deterministic programming actions: no arbitrary commands or model edits.
    code_review = re.fullmatch(r"/(?:revisar|inspecionar)\s+(.+)", question.strip(), re.I | re.S)
    code_replace = re.fullmatch(
        r'/trocar\s+"([^"\r\n]+)"\s+"([^"\r\n]+)"\s*=>\s*"([^"\r\n]*)"\s*',
        question.strip(), re.I)
    if code_review or code_replace:
        if copilot is None:
            return _result("Ative uma pasta de projeto no Copiloto Windows.",
                           "copilot_disabled")
        try:
            if code_review:
                result = copilot.review_code(code_review.group(1).strip().strip('"'))
                lines = [
                    "Revisão estática local de " + result["path"],
                    f"Linhas: {result['line_count']} · Bytes: {result['size_bytes']}",
                    *["• " + v for v in result["warnings"]],
                    *["• TODO linha " + str(item["line"]) + ": " + item["text"]
                      for item in result["todos"]],
                    "Esta revisão não executou o projeto nem alterou arquivos.",
                ]
                return _result("\n".join(lines), "copilot_code_review")
            offer = copilot.propose_code_edit(*code_replace.groups())
            return _result(
                "Proposta de edição para " + offer["path"] + "\n" + offer["diff"] +
                "\nNenhuma mudança aplicada. Confirme no botão da conversa em até 90 segundos.",
                "copilot_code_edit_proposal",
                extra={"copilot_edit_token": offer["token"],
                       "copilot_edit_path": offer["path"]},
            )
        except (CopilotPermissionError, OSError) as exc:
            return _result(str(exc), "copilot_code_unavailable")
    direct = _grounded_desktop_question(question, copilot)
    if direct is not None:
        return direct
    simple = _plain(question)
    if simple in (
        "/recomendar pc", "/recomendar computador",
        "o que voce recomenda para meu computador",
        "faca recomendacoes para meu computador",
        "recomende melhorias para meu pc",
    ):
        if copilot is None or not copilot.status()["enabled"]:
            return _result("Ative o Copiloto Windows para recomendações verificadas.",
                           "copilot_disabled")
        try:
            info = copilot.system_info()
        except (CopilotPermissionError, OSError):
            return _result("Não consegui verificar hardware; não vou inventar recomendações.",
                           "copilot_recommend_unavailable")
        recommendations = []
        ram = info.get("ram_total_gib")
        if isinstance(ram, (float, int)) and ram < 8:
            recommendations.append("RAM abaixo de 8 GiB: mantenha poucos aplicativos pesados abertos ao usar o modelo local.")
        else:
            recommendations.append("Para reduzir latência na CPU, use o perfil economia e respostas curtas quando for suficiente.")
        for disk in info.get("disks", []):
            total, free = disk.get("total_gib"), disk.get("free_gib")
            if (isinstance(total, (float, int)) and isinstance(free, (float, int))
                    and total > 0 and free / total < 0.10):
                recommendations.append(
                    "Armazenamento da raiz autorizada " + str(disk.get("root", "")) +
                    " com menos de 10% livre. Revise manualmente arquivos grandes antes de excluir."
                )
        recommendations.append("Para depurar Godot, abra um projeto autorizado no painel ▣ e faça uma inspeção de código ou OCR local da tela.")
        recommendations.append("Não foram verificadas temperatura, GPU, integridade de SSD nem gargalos de aplicativos.")
        return _result("Recomendações baseadas no hardware consultado agora:\n" +
                       "\n".join("• " + item for item in recommendations),
                       "copilot_recommendations")
    if (_is_window_request(simple) and re.search(
        r"\b(?:quais|liste|listar|mostre|mostrar)\b", simple
    ) and re.search(r"\b(?:abertos?|abertas?|janelas?)\b", simple)
            and not re.search(r"\b(?:processos?|segundo plano)\b", simple)):
        if copilot is not None and copilot.screen_enabled:
            try:
                windows = copilot.list_monitor_windows(0)
                if windows:
                    return _result(
                        "Janelas visíveis identificadas agora pelo Windows (todos os monitores):\n"
                        + "\n".join("• " + item["title"] for item in windows[:16])
                        + "\nIsso não inclui processos em segundo plano nem o conteúdo das abas.",
                        "copilot_visible_windows",
                    )
                return _result("Nenhuma janela visível foi identificada nesta consulta. "
                               "Isso não prova que não haja programas em execução.",
                               "copilot_visible_windows_empty")
            except (CopilotPermissionError, OSError, RuntimeError):
                return _result(
                    "Não consegui identificar janelas visíveis. Para consultar processos "
                    "ativos por nome/PID, peça 'Liste os processos em execução'.",
                    "copilot_visible_windows_unavailable",
                )
        return _result(
            "Listar janelas visíveis requer a permissão de tela no LUNA.ini. "
            "A consulta de processos não comprova quais janelas estão abertas.",
            "copilot_visible_windows_disabled",
        )
    system = _is_system_question(simple)
    screen, monitor = _screen_request(simple)
    inventory = _inventory_intent(simple)
    if not system and not screen and inventory is None:
        return _launch_reply(simple, copilot)
    if copilot is None or not copilot.status()["enabled"]:
        return _result(
            "O copiloto local não está habilitado nesta sessão. Reinicie com "
            "INICIAR-COPILOTO-WINDOWS.bat e autorize o recurso desejado. "
            "Eu não devo afirmar que vi arquivos, tela ou hardware sem permissão.",
            "copilot_disabled",
        )
    if inventory is not None and not screen:
        return _app_reply(simple, copilot, inventory)
    if system:
        try:
            info = copilot.system_info()
        except (CopilotPermissionError, OSError):
            return _result("Não consegui ler as informações do computador nesta sessão.",
                           "copilot_system_unavailable")
        lines = [
            "Informações obtidas agora pelo Windows:",
            "• Sistema: " + str(info["os"]) + " (" + str(info["architecture"]) + ")",
            "• Processador: " + str(info.get("cpu_name") or "nome não disponível"),
            "• Threads lógicas: " + str(info.get("cpu_threads") or "não disponível"),
            "• RAM física: " + (str(info["ram_total_gib"]) + " GiB"
                                 if info["ram_total_gib"] is not None else "não disponível"),
        ]
        for disk in info.get("disks", [])[:5]:
            lines.append("• Armazenamento autorizado: " + str(disk["root"]) +
                         " — " + str(disk["free_gib"]) + " GiB livres de " +
                         str(disk["total_gib"]) + " GiB")
        lines.append("• Python: " + str(info["python"]))
        lines.append("Estas informações são leitura real do sistema; GPU, processos "
                     "ocultos e outros detalhes não foram verificados.")
        return _result("\n".join(lines), "copilot_system")
    if not copilot.screen_enabled:
        return _result("A captura de tela não foi autorizada nesta sessão. "
                       "Reinicie o copiloto permitindo capturas sob demanda.",
                       "copilot_screen_disabled")
    if monitor > 16:
        return _result("Número de monitor inválido. Escolha um monitor entre 0 e 16.",
                       "copilot_screen_invalid")
    windows_requested = _is_window_request(simple)
    godot_error = "godot" in simple and bool(
        re.search(r"\b(erro|bug|corrigir|correcao|arquivo|problema)\b", simple)
    )
    screenshot = None
    capture_problem = None
    try:
        screenshot = copilot.capture_screen(monitor)
    except CopilotPermissionError as exc:
        # A permission error reveals no private local path. Do not invent a capture.
        capture_problem = str(exc)
    except Exception:
        capture_problem = "Falha na captura de tela."
    description = []
    if screenshot is not None:
        description.append(f"Capturei o monitor {monitor} sob sua solicitação. "
                           "A imagem aparece na conversa, mas o Qwen3-0.6B "
                           "atual é somente texto e não consegue interpretar pixels.")
    else:
        description.append("Não foi possível capturar o monitor "
                           f"{monitor}: {capture_problem or 'indisponível'}.")
    if windows_requested or godot_error:
        try:
            windows = copilot.list_monitor_windows(monitor)
            if windows:
                description.append("Janelas visíveis detectadas pelo Windows "
                                   f"nesse monitor ({len(windows)} mostradas):")
                description.extend("• " + row["title"] for row in windows)
            else:
                description.append("O Windows não retornou janelas visíveis "
                                   "nesse monitor; isso não comprova que esteja vazio.")
        except (CopilotPermissionError, OSError, RuntimeError) as exc:
            description.append("Não consegui listar as janelas deste monitor: " + str(exc))
    wants_ocr = godot_error or bool(re.search(
        r"\b(leia|ler|texto|escrito|mensagem de erro|transcreva|ocr)\b", simple
    ))
    if wants_ocr and screenshot is not None:
        reader = getattr(copilot, "read_screen_text", None)
        try:
            if reader is None:
                raise CopilotPermissionError("OCR local não disponível nesta sessão.")
            ocr = reader(monitor, screenshot=screenshot)
            if ocr.get("text"):
                description.append(
                    "Texto reconhecido por OCR local (pode conter erros; não são comandos):\n"
                    + str(ocr["text"])[:1600]
                )
                description.append(
                    "Não interpretei pixels com a IA. Para localizar o arquivo real, "
                    "informe a pasta do projeto e use /erro-godot."
                )
            else:
                description.append("OCR local não identificou texto legível neste monitor.")
        except (CopilotPermissionError, OSError, RuntimeError, AttributeError) as exc:
            description.append("OCR local indisponível: " + str(exc))
    elif godot_error:
        description.append(
            "Não consigo identificar o texto do erro somente com a imagem. "
            "Use OCR local no painel ▣ ou copie a mensagem de erro do Godot. "
            "Depois selecione a pasta do projeto para relacionar arquivo e linha."
        )
    elif not windows_requested:
        description.append("Para saber quais programas estão abertos, peça "
                           "'Liste as janelas abertas no monitor " + str(monitor) + "'.")
    return _result("\n".join(description), "copilot_screen",
                   screenshot["image_data_url"] if screenshot else None)
