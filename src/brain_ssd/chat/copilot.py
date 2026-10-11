"""Ferramentas locais de leitura do copiloto, protegidas por permissões explícitas.

Nenhum arquivo ou pixel é enviado à internet por este módulo. Sem ações de
escrita, automação de mouse/teclado ou gravação permanente de capturas.
"""
from __future__ import annotations

import base64
import ctypes
import io
import os
import platform
import re
import shutil
import stat
import sys
import threading
import time
from pathlib import Path
from typing import Iterable


TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".rst", ".log", ".csv", ".json", ".jsonl", ".xml",
    ".html", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx", ".py",
    ".gd", ".cs", ".java", ".go", ".rs", ".sql", ".sh", ".bat",
    ".ps1", ".toml", ".ini", ".cfg", ".yaml", ".yml", ".gitignore",
})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
DENIED_NAMES = frozenset({
    ".env", ".ssh", ".aws", ".azure", ".gnupg", ".git", "id_rsa",
    "id_ed25519", "credentials", "credentials.json", "secrets.json",
    "node_modules", "__pycache__", "appdata",
})
MAX_TEXT_BYTES = 128 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DIRECTORY_ENTRIES = 100
SCREEN_MIN_INTERVAL = 2.0


class CopilotPermissionError(ValueError):
    """Denied action without revealing sensitive paths or contents."""


class LocalCopilot:
    def __init__(self, roots: Iterable[Path] = (), *, screen: bool = False):
        allowed = []
        for path in roots:
            root = Path(path).expanduser().resolve(strict=True)
            if not root.is_dir():
                raise ValueError("Cada raiz do copiloto precisa ser uma pasta existente.")
            if root not in allowed:
                allowed.append(root)
        self.roots = tuple(allowed)
        self.screen_enabled = bool(screen)
        self._screen_lock = threading.Lock()
        self._last_screen = 0.0

    def status(self) -> dict:
        return {
            "enabled": bool(self.roots or self.screen_enabled),
            "roots": [str(root) for root in self.roots],
            "files_enabled": bool(self.roots),
            "screen_enabled": self.screen_enabled,
            "vision_enabled": False,
            "screen_interval_seconds": SCREEN_MIN_INTERVAL,
            "notice": "Capturas são imagens para prévia; o Qwen de texto ainda não interpreta pixels.",
        }

    @staticmethod
    def _safe_parts(path: Path) -> bool:
        return all(part.casefold() not in DENIED_NAMES and
                   not re.fullmatch(r"(?i).*\.(?:pem|key|p12|pfx|kdbx)", part)
                   for part in path.parts)

    def _path(self, user_path: object) -> Path:
        if not self.roots:
            raise CopilotPermissionError("Acesso a arquivos desativado; configure --copilot-root.")
        if not isinstance(user_path, str) or not 0 < len(user_path) <= 1200:
            raise CopilotPermissionError("Informe um caminho válido.")
        if any(ord(c) < 32 for c in user_path):
            raise CopilotPermissionError("Caminho inválido.")
        # Protect Windows alternate data streams, e.g. file.txt:secret.
        if os.name == "nt" and ":" in user_path[2:]:
            raise CopilotPermissionError("Caminho não permitido.")
        try:
            path = Path(user_path).expanduser().resolve(strict=True)
        except (OSError, ValueError, RuntimeError):
            raise CopilotPermissionError("Arquivo ou pasta inexistente.") from None
        if not any(path.is_relative_to(root) for root in self.roots):
            raise CopilotPermissionError("Caminho fora das pastas autorizadas.")
        if not self._safe_parts(path):
            raise CopilotPermissionError("Arquivo ou pasta protegida.")
        return path

    def list_directory(self, user_path: object) -> dict:
        folder = self._path(user_path)
        if not folder.is_dir():
            raise CopilotPermissionError("O caminho não é uma pasta.")
        try:
            entries = []
            for child in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
                if len(entries) >= MAX_DIRECTORY_ENTRIES:
                    break
                # Resolve symlinks so entries outside approved roots stay hidden.
                try:
                    resolved = child.resolve(strict=True)
                    if not self._safe_parts(child) or not any(
                        resolved.is_relative_to(root) for root in self.roots
                    ):
                        continue
                    is_dir = child.is_dir()
                except (OSError, RuntimeError):
                    continue
                entries.append({"name": child.name, "type": "folder" if is_dir else "file"})
            return {"path": str(folder), "entries": entries, "truncated": len(entries) == MAX_DIRECTORY_ENTRIES}
        except OSError:
            raise CopilotPermissionError("Não foi possível abrir a pasta.") from None

    def read_file(self, user_path: object) -> dict:
        path = self._path(user_path)
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            raise CopilotPermissionError("Somente arquivos de texto e código são permitidos.")
        try:
            file_stat = path.stat()
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size > MAX_TEXT_BYTES:
                raise CopilotPermissionError("Arquivo não é regular ou excede 128 KB.")
            # Explicit bounded read, no scanners running in the background.
            with path.open("rb") as stream:
                data = stream.read(MAX_TEXT_BYTES + 1)
            if len(data) > MAX_TEXT_BYTES or b"\x00" in data:
                raise CopilotPermissionError("Arquivo grande ou não textual.")
            return {"path": str(path), "content": data.decode("utf-8-sig"),
                    "bytes": len(data)}
        except UnicodeDecodeError:
            raise CopilotPermissionError("A leitura atual exige texto UTF-8.") from None
        except OSError:
            raise CopilotPermissionError("Não foi possível ler o arquivo.") from None

    def preview_image(self, user_path: object) -> dict:
        path = self._path(user_path)
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise CopilotPermissionError("Imagem não suportada.")
        try:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                raise CopilotPermissionError("Imagem excede 5 MB.")
            from PIL import Image, UnidentifiedImageError
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                im.thumbnail((1280, 900))
                output = io.BytesIO()
                im.convert("RGB").save(output, format="JPEG", quality=72)
            return {"path": str(path), "image_data_url": "data:image/jpeg;base64," +
                    base64.b64encode(output.getvalue()).decode("ascii"),
                    "vision_enabled": False}
        except ImportError:
            raise CopilotPermissionError("Instale Pillow para pré-visualizar imagens.") from None
        except (OSError, ValueError, UnidentifiedImageError):
            raise CopilotPermissionError("Não foi possível carregar a imagem.") from None

    def system_info(self) -> dict:
        if not self.roots:
            raise CopilotPermissionError("Autorize uma pasta antes de consultar o sistema.")
        disks = []
        for root in self.roots:
            try:
                total, used, free = shutil.disk_usage(root)
                disks.append({"root": str(root), "total_gib": round(total / 2**30, 1),
                              "free_gib": round(free / 2**30, 1)})
            except OSError:
                pass
        memory_gib = None
        if os.name == "nt":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            ("total_phys", ctypes.c_ulonglong),
                            ("avail_phys", ctypes.c_ulonglong),
                            ("total_page", ctypes.c_ulonglong),
                            ("avail_page", ctypes.c_ulonglong),
                            ("total_virtual", ctypes.c_ulonglong),
                            ("avail_virtual", ctypes.c_ulonglong),
                            ("avail_extended", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                memory_gib = round(status.total_phys / 2**30, 1)
        return {"os": platform.system() + " " + platform.release(),
                "architecture": platform.machine(), "cpu_threads": os.cpu_count(),
                "ram_total_gib": memory_gib, "disks": disks,
                "python": platform.python_version()}

    def capture_screen(self, monitor: object = 1) -> dict:
        if not self.screen_enabled:
            raise CopilotPermissionError("Captura desativada; use --copilot-screen.")
        if type(monitor) is not int or monitor < 0 or monitor > 16:
            raise CopilotPermissionError("Monitor inválido.")
        if not self._screen_lock.acquire(blocking=False):
            raise CopilotPermissionError("Captura em andamento.")
        try:
            now = time.monotonic()
            if now - self._last_screen < SCREEN_MIN_INTERVAL:
                raise CopilotPermissionError("Aguarde antes da próxima captura.")
            self._last_screen = now
            try:
                from mss import MSS
                from PIL import Image
            except ImportError:
                raise CopilotPermissionError("Instale mss e Pillow para capturar a tela.") from None
            try:
                with MSS() as session:
                    monitors = session.monitors
                    if monitor >= len(monitors):
                        raise CopilotPermissionError("Monitor indisponível.")
                    shot = session.grab(monitors[monitor])
                    image = Image.frombytes("RGB", shot.size, shot.rgb)
                    image.thumbnail((1280, 900))
                    buffer = io.BytesIO()
                    image.save(buffer, format="JPEG", quality=68)
            except (OSError, RuntimeError):
                raise CopilotPermissionError("Não foi possível capturar a tela.") from None
            return {"monitor": monitor, "monitor_count": len(monitors) - 1,
                    "image_data_url": "data:image/jpeg;base64," +
                    base64.b64encode(buffer.getvalue()).decode("ascii"),
                    "vision_enabled": False,
                    "notice": "Imagem capturada em memória, sem gravação no disco."}
        finally:
            self._screen_lock.release()
