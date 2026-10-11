"""Deterministic, truthful Copilot routes for explicit Windows questions.

The Qwen text-only model never receives pixels and cannot invent monitor
contents. The image, if any, is returned for local UI preview only.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from brain_ssd.chat.copilot import CopilotPermissionError, LocalCopilot


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return " ".join(normalized.split())


def _result(answer: str, action: str, image_data_url: str | None = None) -> dict[str, Any]:
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


def copilot_answer(question: str, copilot: LocalCopilot | None) -> dict[str, Any] | None:
    """Return a truthful local result only for clearly selected Copilot intents."""
    if not isinstance(question, str):
        return None
    simple = _plain(question)
    system = _is_system_question(simple)
    screen, monitor = _screen_request(simple)
    if not system and not screen:
        return None
    if copilot is None or not copilot.status()["enabled"]:
        return _result(
            "O copiloto local não está habilitado nesta sessão. Reinicie com "
            "INICIAR-COPILOTO-WINDOWS.bat e autorize o recurso desejado. "
            "Eu não devo afirmar que vi arquivos, tela ou hardware sem permissão.",
            "copilot_disabled",
        )
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
    if godot_error:
        description.append(
            "Não consegui ler o texto do erro no Godot apenas com a captura. "
            "Para identificar a linha e o arquivo sem inventar, copie o erro "
            "do painel do Godot e selecione o arquivo do projeto no painel ▣. "
            "A leitura dos pixels exige um módulo de visão/OCR que ainda não está integrado."
        )
    elif not windows_requested:
        description.append("Para saber quais programas estão abertos, peça "
                           "'Liste as janelas abertas no monitor " + str(monitor) + "'.")
    return _result("\n".join(description), "copilot_screen",
                   screenshot["image_data_url"] if screenshot else None)
