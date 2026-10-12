"""Explicitly approved, bounded Godot script parser verification.

This runs a REAL installed Godot executable against an authorized user project.
It is NOT an OS sandbox. Godot startup can load project/editor extensions and
may write import/cache files. Execution is disabled unless configured at launch,
requires an individual single-use confirmation, and never runs arbitrary shell.
"""
from __future__ import annotations

import os
import secrets
import stat
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from brain_ssd.chat.copilot import CopilotPermissionError

MAX_OUTPUT = 12000
MAX_SECONDS = 30
EXPIRES_SECONDS = 90


class GodotValidator:
    def __init__(self, copilot: Any, binary: Path):
        self.copilot = copilot
        resolved = Path(binary).expanduser().resolve(strict=True)
        if (not resolved.is_file() or resolved.is_symlink()
                or resolved.suffix.casefold() != ".exe"
                or "godot" not in resolved.stem.casefold()):
            raise ValueError("Selecione um executável Godot .exe real e não um link.")
        self.binary = resolved
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._offers: dict[str, dict[str, Any]] = {}

    def _target(self, project: object, script: object) -> tuple[Path, Path, str]:
        if not isinstance(project, str) or not isinstance(script, str):
            raise CopilotPermissionError("Projeto e arquivo .gd devem ser informados.")
        inspector = self.copilot._godot_inspector()
        root = inspector._project_path(project)
        relative = script.removeprefix("res://").replace("\\", "/")
        if (not relative or relative.startswith("/")
                or any(part in ("", ".", "..") for part in relative.split("/"))
                or not relative.casefold().endswith(".gd") or len(relative) > 260):
            raise CopilotPermissionError("Informe um script .gd dentro do projeto.")
        path = self.copilot._path(str(root / relative))
        if not path.is_file() or path.suffix.casefold() != ".gd":
            raise CopilotPermissionError("Script Godot não encontrado.")
        if path.is_symlink() or Path(project).is_symlink():
            raise CopilotPermissionError("Não execute verificações por links simbólicos.")
        return root, path, "res://" + path.relative_to(root).as_posix()

    @staticmethod
    def _signature(path: Path) -> tuple[int, int, int]:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise CopilotPermissionError("Um arquivo de verificação mudou de tipo.")
        return info.st_size, info.st_mtime_ns, getattr(info, "st_ino", 0)

    def propose(self, project: object, script: object) -> dict[str, Any]:
        root, path, resource = self._target(project, script)
        token = secrets.token_urlsafe(32)
        offer = {
            "root": str(root),
            "script": resource,
            "path": str(path),
            "script_signature": self._signature(path),
            "manifest_signature": self._signature(root / "project.godot"),
            "binary_signature": self._signature(self.binary),
            "expires": time.monotonic() + EXPIRES_SECONDS,
        }
        with self._lock:
            self._offers.clear()
            self._offers[token] = offer
        return {
            "token": token,
            "project": str(root),
            "script": resource,
            "binary": str(self.binary),
            "expires_seconds": EXPIRES_SECONDS,
            "timeout_seconds": MAX_SECONDS,
            "command_flags": ["--headless", "--recovery-mode",
                              "--path", "<project>", "--script", resource,
                              "--check-only"],
            "warning": (
                "Godot poderá inicializar código/editor plugins ou escrever cache "
                "na pasta do projeto. Não há sandbox de sistema. Só prossiga com "
                "projetos confiáveis e após verificar o executável configurado."
            ),
        }

    def confirm(self, token: object) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 200:
            raise CopilotPermissionError("Token de verificação inválido.")
        with self._lock:
            offer = self._offers.pop(token, None)
        if offer is None or time.monotonic() > offer["expires"]:
            raise CopilotPermissionError("Pedido vencido ou já confirmado.")
        root, path, resource = self._target(offer["root"], offer["script"])
        if (str(root) != offer["root"] or str(path) != offer["path"]
                or resource != offer["script"]
                or self._signature(path) != offer["script_signature"]
                or self._signature(root / "project.godot") != offer["manifest_signature"]
                or self._signature(self.binary) != offer["binary_signature"]):
            raise CopilotPermissionError(
                "Arquivo, projeto ou Godot mudou após a autorização. Prepare outro teste."
            )
        if not self._run_lock.acquire(blocking=False):
            raise CopilotPermissionError("Uma verificação Godot já está em execução.")
        start = time.monotonic()
        try:
            # Absolute binary path and fixed argument vector. NO shell,
            # no user-controlled extra flags or scripts outside the project.
            args = [str(self.binary), "--headless", "--recovery-mode",
                    "--path", str(root), "--script", resource, "--check-only"]
            try:
                result = subprocess.run(
                    args, cwd=str(root), shell=False,
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, timeout=MAX_SECONDS, check=False,
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "TIMEOUT", "exit_code": None,
                    "duration_seconds": round(time.monotonic() - start, 2),
                    "script": resource,
                    "output": "Godot não concluiu dentro do limite. Processo interrompido.",
                    "notice": "Timeout não comprova que o script está correto ou incorreto.",
                }
            except OSError:
                raise CopilotPermissionError("Não foi possível iniciar o Godot configurado.") from None
            import locale
            output = result.stdout.decode(locale.getpreferredencoding(False),
                                          errors="replace")
            if len(output) > MAX_OUTPUT:
                output = output[:MAX_OUTPUT] + "\n[saída truncada]"
            return {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "exit_code": result.returncode,
                "duration_seconds": round(time.monotonic() - start, 2),
                "script": resource,
                "output": output,
                "notice": (
                    "PASS significa que o processo Godot retornou código zero "
                    "em --check-only, não que o jogo foi testado ou ficou sem bugs."
                ),
            }
        finally:
            self._run_lock.release()
