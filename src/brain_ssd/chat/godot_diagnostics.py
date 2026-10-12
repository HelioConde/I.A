"""Read-only, bounded Godot project inspection and stacktrace correlation.

No shell, Godot launch, AI-generated edits, network calls or persistent logs.
Only projects inside a root explicitly authorized in LocalCopilot can be read.
"""
from __future__ import annotations

import os
import re
from collections import deque
from pathlib import Path, PurePosixPath
from typing import Any

from brain_ssd.chat.copilot import CopilotPermissionError

MAX_DIRS = 180
MAX_ENTRIES = 3500
MAX_FILES = 250
MAX_DEPTH = 8
MAX_SCRIPT_BYTES = 96 * 1024
MAX_ERROR_CHARS = 4000
ALLOWED = frozenset({".gd", ".tscn", ".tres", ".cs"})
SKIP_FOLDERS = frozenset({
    ".git", ".godot", ".svn", ".hg", ".ssh", ".aws", ".azure",
    ".gnupg", "node_modules", "__pycache__", "appdata",
})
RESOURCE = re.compile(
    r"res://(?P<path>[A-Za-z0-9_./() @+\-]+?\.(?:gd|tscn|tres|cs))"
    r"(?:\s*:\s*(?P<line>\d{1,7}))?",
    re.IGNORECASE,
)
BASENAME = re.compile(
    r"(?<![a-zA-Z0-9_/])(?P<name>[A-Za-z_][\w-]*\.(?:gd|cs))"
    r"(?:\s*:\s*(?P<line>\d{1,7}))?",
    re.IGNORECASE,
)


def _safe_resource(value: str) -> str | None:
    name = value.replace("\\", "/").strip("/")
    p = PurePosixPath(name)
    if (not name or len(name) > 260 or p.is_absolute()
            or any(part in ("", ".", "..") or part.casefold() in SKIP_FOLDERS
                   for part in p.parts)):
        return None
    return p.as_posix()


def _read_lines(path: Path) -> list[str] | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_SCRIPT_BYTES:
            return None
        raw = path.read_bytes()
        if b"\x00" in raw or len(raw) > MAX_SCRIPT_BYTES:
            return None
        return raw.decode("utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError, ValueError):
        return None


class GodotInspector:
    def __init__(self, copilot: Any):
        self.copilot = copilot

    def _project_path(self, user_path: object) -> Path:
        root = self.copilot._path(user_path)
        if not root.is_dir() or not (root / "project.godot").is_file():
            raise CopilotPermissionError("Selecione uma pasta com project.godot.")
        manifest = root / "project.godot"
        if manifest.is_symlink():
            raise CopilotPermissionError("Manifesto de projeto por link simbólico não é permitido.")
        self.copilot._path(str(manifest))
        return root

    def _scan(self, root: Path) -> tuple[list[str], bool, int]:
        queue = deque([(root, 0)])
        files: list[str] = []
        visited = 0
        dirs = 0
        truncated = False
        while queue:
            folder, depth = queue.popleft()
            dirs += 1
            if dirs > MAX_DIRS:
                truncated = True
                break
            try:
                with os.scandir(folder) as iterator:
                    entries = sorted(iterator, key=lambda e: e.name.casefold())
            except OSError:
                continue
            for entry in entries:
                visited += 1
                if visited > MAX_ENTRIES:
                    truncated = True
                    break
                name = entry.name
                if name.casefold() in SKIP_FOLDERS or name.startswith("."):
                    continue
                try:
                    if entry.is_symlink():
                        continue
                    candidate = Path(entry.path)
                    # Path guard enforces authorized roots and blocked secrets.
                    self.copilot._path(str(candidate))
                    if entry.is_dir(follow_symlinks=False):
                        if depth < MAX_DEPTH:
                            queue.append((candidate, depth + 1))
                        else:
                            truncated = True
                    elif entry.is_file(follow_symlinks=False) and candidate.suffix.casefold() in ALLOWED:
                        files.append(candidate.relative_to(root).as_posix())
                        if len(files) >= MAX_FILES:
                            truncated = True
                            break
                except (OSError, CopilotPermissionError, ValueError):
                    continue
            if truncated:
                break
        return sorted(files, key=str.casefold), truncated, visited

    def inspect(self, user_path: str) -> dict[str, Any]:
        root = self._project_path(user_path)
        files, truncated, visited = self._scan(root)
        scripts = [name for name in files if name.casefold().endswith((".gd", ".cs"))]
        todos: list[dict[str, Any]] = []
        for rel in scripts[:70]:
            lines = _read_lines(root / rel)
            if lines is None:
                continue
            for index, line in enumerate(lines, 1):
                if re.search(r"\b(?:TODO|FIXME)\b", line):
                    todos.append({"file": rel, "line": index,
                                  "note": line.strip()[:120]})
                    if len(todos) >= 12:
                        break
            if len(todos) >= 12:
                break
        return {
            "project_root": str(root),
            "project_manifest": "project.godot",
            "file_count": len(files),
            "script_count": len(scripts),
            "scene_count": sum(name.casefold().endswith(".tscn") for name in files),
            "resources_count": sum(name.casefold().endswith(".tres") for name in files),
            "files": files[:75], "todo": todos,
            "scanned_entries": visited, "truncated": truncated or len(files) > 75,
            "recommendations": [
                "Use a mensagem de erro real do Godot com o projeto autorizado para localizar o arquivo/linha.",
                "Examine TODO/FIXME manualmente; eles não são bugs comprovados.",
                "Antes de editar, mostre um diff e confirme a alteração com backup.",
            ],
            "notice": "Leitura estática limitada. Não executou Godot, não testou o jogo "
                      "nem verificou erros de compilação.",
        }

    def diagnose(self, user_path: str, error_text: str) -> dict[str, Any]:
        if not isinstance(error_text, str) or not 0 < len(error_text.strip()) <= MAX_ERROR_CHARS:
            raise CopilotPermissionError("Cole uma mensagem de erro com até 4.000 caracteres.")
        root = self._project_path(user_path)
        files, truncated, _ = self._scan(root)
        indexed = {s.casefold(): s for s in files}
        basename_index: dict[str, list[str]] = {}
        for rel in files:
            basename_index.setdefault(Path(rel).name.casefold(), []).append(rel)
        findings: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for match in RESOURCE.finditer(error_text):
            raw = _safe_resource(match.group("path"))
            if raw is None:
                continue
            rel = indexed.get(raw.casefold())
            if rel is None:
                continue
            line = int(match.group("line") or 0)
            if (rel.casefold(), line) in seen:
                continue
            seen.add((rel.casefold(), line))
            findings.append(self._reference(root, rel, line, "res:// identificado no erro"))
            if len(findings) >= 6:
                break
        if not findings:
            for match in BASENAME.finditer(error_text):
                choices = basename_index.get(match.group("name").casefold(), [])
                if len(choices) != 1:
                    continue
                rel = choices[0]
                line = int(match.group("line") or 0)
                if (rel.casefold(), line) in seen:
                    continue
                seen.add((rel.casefold(), line))
                findings.append(self._reference(root, rel, line,
                                                 "Nome de arquivo único no projeto"))
                if len(findings) >= 6:
                    break
        advice = ["Nenhum arquivo foi alterado ou executado."]
        normalized = error_text.casefold()
        if "null instance" in normalized or "nil" in normalized or "null" in normalized:
            advice.append("Mensagem menciona null/nil: confira se a variável e o nó foram inicializados antes do acesso.")
        if "parse error" in normalized or "parser error" in normalized:
            advice.append("O erro parece ser de análise sintática: confira a linha citada e as anteriores.")
        if "invalid access" in normalized or "invalid get index" in normalized:
            advice.append("Confirme o tipo real do objeto e a existência da propriedade antes de acessar.")
        if not findings:
            advice.append("Não foi possível vincular o erro a um arquivo único e autorizado. "
                          "Copie do Godot a mensagem completa com res://caminho.gd:linha.")
        if truncated:
            advice.append("Busca parcial: limite de diretórios/arquivos atingido. Reduza o escopo da pasta.")
        return {
            "project_root": str(root), "matches": findings,
            "matched_count": len(findings), "truncated": truncated,
            "recommendations": advice,
            "notice": "Diagnóstico baseado no texto do erro e nos arquivos reais. "
                      "Não é correção automática nem verificação de execução.",
        }

    def _reference(self, root: Path, rel: str, requested_line: int,
                   evidence: str) -> dict[str, Any]:
        target = self.copilot._path(str(root / rel))
        lines = _read_lines(target)
        snippets: list[dict[str, Any]] = []
        if lines is not None and 0 < requested_line <= len(lines):
            for idx in range(max(1, requested_line - 3), min(len(lines), requested_line + 3) + 1):
                snippets.append({"line": idx, "text": lines[idx - 1][:220]})
        return {
            "file": rel, "path": str(target),
            "reported_line": requested_line or None,
            "source": evidence, "snippet": snippets,
            "readable": lines is not None,
            "notice": "A associação não prova a causa do erro.",
        }
