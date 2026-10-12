"""Consent-based, transaction-like file editing for the Windows coding copilot.

Never execute project source code or invoke an external command. A human must
preview a bounded diff and confirm it using a short-lived single-use token.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import os
import secrets
import stat
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from brain_ssd.chat.copilot import CopilotPermissionError, MAX_TEXT_BYTES

EDITABLE_EXTENSIONS = frozenset({
    ".gd", ".py", ".js", ".jsx", ".ts", ".tsx", ".css",
    ".html", ".json", ".md", ".toml", ".yaml", ".yml", ".cs",
})
MAX_EDIT_BYTES = 80 * 1024
MAX_REPLACE_BYTES = 8000
MAX_DIFF_BYTES = 18_000
MAX_PENDING_AGE = 90


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _backup_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or
                str(Path.home() / ".local" / "share"))
    return base / "BrainSSD" / "code-edit-backups"


class CodeEditor:
    def __init__(self, copilot: Any):
        self.copilot = copilot
        self._lock = threading.Lock()
        self._offers: dict[str, dict[str, Any]] = {}

    def _allowed(self, user_path: str) -> Path:
        if not self.copilot.edit_enabled:
            raise CopilotPermissionError("Edição de código não autorizada nesta sessão.")
        path = self.copilot._path(user_path)
        if not path.is_file() or path.suffix.casefold() not in EDITABLE_EXTENSIONS:
            raise CopilotPermissionError("Somente arquivos de código permitidos podem ser editados.")
        # Refuse symlink (including directory reparse points in supplied path)
        original = Path(user_path).expanduser()
        for item in (original, *original.parents):
            if item.is_symlink() and item not in self.copilot.roots:
                raise CopilotPermissionError("Não edite arquivos por links simbólicos.")
        return path

    def _read(self, path: Path) -> bytes:
        try:
            st = path.stat()
            if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_EDIT_BYTES:
                raise CopilotPermissionError("Arquivo não é regular ou excede 80 KB.")
            with path.open("rb") as stream:
                raw = stream.read(MAX_EDIT_BYTES + 1)
            if len(raw) > MAX_EDIT_BYTES or b"\x00" in raw:
                raise CopilotPermissionError("Arquivo não é UTF-8 textual.")
            raw.decode("utf-8-sig")
            return raw
        except UnicodeDecodeError:
            raise CopilotPermissionError("Arquivos editáveis precisam ser UTF-8.") from None
        except OSError:
            raise CopilotPermissionError("Não foi possível ler o arquivo de código.") from None

    def recommend(self, user_path: str) -> dict[str, Any]:
        path = self.copilot._path(user_path)
        if path.suffix.casefold() not in EDITABLE_EXTENSIONS:
            raise CopilotPermissionError("Selecione um arquivo de código permitido.")
        raw = self._read(path)
        content = raw.decode("utf-8-sig")
        lines = content.splitlines()
        todo = [(i, line.strip()[:130]) for i, line in enumerate(lines, 1)
                if "TODO" in line or "FIXME" in line][:8]
        warnings: list[str] = []
        if path.suffix.casefold() == ".py":
            try:
                ast.parse(content, filename=path.name)
            except SyntaxError as exc:
                warnings.append(f"Sintaxe Python: linha {exc.lineno}, {exc.msg}")
        long_lines = sum(len(line) > 120 for line in lines)
        if long_lines:
            warnings.append(f"{long_lines} linha(s) ultrapassam 120 caracteres.")
        if not content.endswith("\n"):
            warnings.append("Arquivo sem quebra de linha final.")
        if not warnings and not todo:
            warnings.append("Nenhum problema detectado nas verificações estáticas limitadas.")
        return {
            "path": str(path), "line_count": len(lines),
            "size_bytes": len(raw), "warnings": warnings,
            "todos": [{"line": i, "text": line} for i, line in todo],
            "notice": "Inspeção estática limitada; não executa nem compreende integralmente o projeto.",
        }

    def propose(self, user_path: str, before: str, after: str) -> dict[str, Any]:
        path = self._allowed(user_path)
        if not isinstance(before, str) or not isinstance(after, str):
            raise CopilotPermissionError("Informe o trecho original e a substituição.")
        if (not before or before == after or len(before.encode("utf-8")) > MAX_REPLACE_BYTES
                or len(after.encode("utf-8")) > MAX_REPLACE_BYTES or "\x00" in before + after):
            raise CopilotPermissionError("Trecho de edição vazio, idêntico ou grande demais.")
        old = self._read(path)
        try:
            # Preserve BOM if present; only change the explicitly selected text.
            text = old.decode("utf-8-sig")
            if text.count(before) != 1:
                raise CopilotPermissionError(
                    "O trecho original deve aparecer exatamente uma vez no arquivo.")
            newer = text.replace(before, after, 1)
            newer_raw = (b"\xef\xbb\xbf" if old.startswith(b"\xef\xbb\xbf") else b"") + newer.encode("utf-8")
            if len(newer_raw) > MAX_EDIT_BYTES:
                raise CopilotPermissionError("Arquivo editado excederia 80 KB.")
            diff = "".join(difflib.unified_diff(
                text.splitlines(keepends=True), newer.splitlines(keepends=True),
                fromfile="antes/" + path.name, tofile="depois/" + path.name,
            ))
            if not diff or len(diff.encode("utf-8")) > MAX_DIFF_BYTES:
                raise CopilotPermissionError("Diferença muito grande; reduza o trecho.")
        except UnicodeError:
            raise CopilotPermissionError("Edição exige texto UTF-8.") from None
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._offers.clear()
            self._offers[token] = {
                "path": str(path), "expected_sha": _digest(old),
                "new_bytes": newer_raw, "expires": time.monotonic() + MAX_PENDING_AGE,
            }
        return {"token": token, "path": str(path), "diff": diff,
                "expires_seconds": MAX_PENDING_AGE,
                "notice": "Nenhum arquivo foi alterado. Confira a diferença e confirme."}

    def apply(self, token: object) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 200:
            raise CopilotPermissionError("Confirmação de edição inválida.")
        with self._lock:
            offer = self._offers.pop(token, None)
            if offer is None or time.monotonic() > offer["expires"]:
                raise CopilotPermissionError("Edição expirada ou já utilizada.")
            path = self._allowed(offer["path"])
            old = self._read(path)
            if _digest(old) != offer["expected_sha"]:
                raise CopilotPermissionError("Arquivo alterado após a prévia; nenhuma edição aplicada.")
            # A private backup is written BEFORE replacing the original.
            backup_dir = _backup_dir()
            try:
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup = backup_dir / (_digest(str(path).encode())[:14] + "-" +
                                       secrets.token_hex(8) + path.suffix + ".bak")
                with backup.open("xb") as stream:
                    stream.write(old)
                try:
                    backup.chmod(0o600)
                except OSError:
                    pass
                fd, temp_path = tempfile.mkstemp(
                    prefix=".brainssd-edit-", suffix=path.suffix, dir=path.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(offer["new_bytes"])
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.chmod(temp_path, stat.S_IMODE(path.stat().st_mode))
                    # Guard against simple concurrent modification before swap.
                    if _digest(self._read(path)) != offer["expected_sha"]:
                        raise CopilotPermissionError("Arquivo alterado antes da aplicação.")
                    os.replace(temp_path, path)
                finally:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            except OSError:
                raise CopilotPermissionError("Falha ao gravar backup ou atualizar arquivo.") from None
        return {"status": "applied", "path": str(path),
                "backup_path": str(backup), "new_sha256": _digest(offer["new_bytes"]),
                "notice": "Edição aplicada após confirmação. Backup privado criado."}
