"""Safe, actionable startup diagnostics for the local Windows model.

The loopback HTTP status must never expose arbitrary native error messages,
paths, model text or a Python traceback. Only allowlisted codes/hints appear.
Detailed local preflight is run separately via doctor_chat.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RECOVERY: dict[str, str] = {
    "MODEL_MISSING": "Modelo GGUF ausente. Verifique models/Qwen3-0.6B-Q8_0.gguf e rode DIAGNOSTICAR-CHAT-WINDOWS.bat.",
    "MODEL_INVALID": "O GGUF está incompleto ou inválido. Confira o tamanho e o arquivo original, sem apagar suas memórias.",
    "CORE_MISSING": "Executável llama-completion ausente no perfil Economia. Rode DIAGNOSTICAR-CHAT-WINDOWS.bat.",
    "SERVER_MISSING": "Executável llama-server ausente no perfil Rápido. Rode DIAGNOSTICAR-CHAT-WINDOWS.bat.",
    "MODEL_UNREADABLE": "O arquivo do modelo não pôde ser lido. Verifique permissões e bloqueio por antivírus.",
    "RUNTIME_UNREADABLE": "O executável local não pôde ser iniciado. Verifique permissões, arquitetura e dependências do Windows.",
    "STARTUP_UNEXPECTED": "Falha não classificada ao preparar o Core. Rode o diagnóstico local e compartilhe apenas o ZIP sanitizado.",
}


class ChatStartupError(RuntimeError):
    """Safe preflight failure; code carries no local path or private text."""

    def __init__(self, code: str):
        if code not in RECOVERY:
            raise ValueError("Invalid startup diagnostic code")
        super().__init__(RECOVERY[code])
        self.code = code


@dataclass(frozen=True)
class StartupDiagnosis:
    code: str
    guidance: str


def classify_startup_error(error: BaseException) -> StartupDiagnosis:
    """Classify only trusted exception types and fixed, known error phrases."""
    if isinstance(error, ChatStartupError):
        code = error.code
    elif isinstance(error, FileNotFoundError):
        # Backward compatibility with older runtime adapters. Never expose
        # arbitrary native filenames from the exception.
        message = str(error).casefold()
        code = ("CORE_MISSING" if "llama-completion" in message or "llama-cli" in message
                else "SERVER_MISSING" if "llama-server" in message
                else "MODEL_MISSING" if "gguf" in message or "modelo" in message
                else "STARTUP_UNEXPECTED")
    elif isinstance(error, ValueError) and "gguf" in str(error).casefold():
        code = "MODEL_INVALID"
    elif isinstance(error, PermissionError):
        code = "RUNTIME_UNREADABLE"
    elif isinstance(error, OSError):
        code = "RUNTIME_UNREADABLE"
    else:
        code = "STARTUP_UNEXPECTED"
    return StartupDiagnosis(code, RECOVERY[code])
