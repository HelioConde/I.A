"""Luna Code Studio: bounded, human-approved proposals for original projects.

Preview never mutates the workspace, and generated code is never executed.
The module is independent from frozen Brain-SSD research experiments.
"""
from __future__ import annotations

import ast
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any

MAX_FILES = 20
MAX_FILE_BYTES = 48000
MAX_TOTAL_BYTES = 250000
ALLOWED_EXTENSIONS = {".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".py",
                      ".json", ".md", ".txt", ".svg"}
BLOCKED_PARTS = {".git", ".github", "node_modules", "__pycache__", "dist",
                 "build", "models", "brain_data", "results", "secrets"}
BLOCKED_NAMES = {".env", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                    *(f"lpt{i}" for i in range(1, 10))}


class ProposalError(ValueError):
    """Reject unsafe, malformed, or unreviewable generated content."""


class HTMLSignals(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: set[str] = set()
        self.has_lang = False
        self.has_viewport = False
        self.has_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.add(tag)
        attrs_map = dict(attrs)
        if tag == "html" and attrs_map.get("lang"):
            self.has_lang = True
        if tag == "meta" and (attrs_map.get("name") or "").lower() == "viewport":
            self.has_viewport = True
        if tag == "title":
            self.has_title = True


def validate_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not 1 <= len(value) <= 180:
        raise ProposalError("Caminho de arquivo inválido.")
    if (value.startswith("/") or "\\" in value or ":" in value or "\x00" in value
            or any(ord(c) < 32 for c in value) or "//" in value or value.endswith("/")):
        raise ProposalError("Use caminho relativo POSIX sem caracteres especiais.")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.startswith(".") or part.endswith((" ", "."))
           or part.casefold() in BLOCKED_PARTS
           or part.split(".")[0].casefold() in WINDOWS_RESERVED for part in parts):
        raise ProposalError("Caminho protegido, oculto ou reservado.")
    path = PurePosixPath(value)
    if path.name.casefold() in BLOCKED_NAMES or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ProposalError("Tipo ou nome de arquivo bloqueado.")
    return path


def parse_proposal(raw: str) -> dict[str, Any]:
    """Parse a complete JSON object, not partial code fences or tool commands."""
    if not isinstance(raw, str) or not raw.strip():
        raise ProposalError("Proposta vazia.")
    raw = raw.strip()
    fenced = re.fullmatch(r"\x60\x60\x60json\s*\n(.*?)\n\x60\x60\x60", raw, re.I | re.S)
    if fenced:
        raw = fenced.group(1)
    if re.search(r"</?think>", raw, re.I):
        raise ProposalError("Modelo retornou marcador interno de raciocínio.")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ProposalError("A saída não é JSON válido e completo.") from exc
    if not isinstance(data, dict) or set(data) != {"version", "goal", "files"}:
        raise ProposalError("Contrato esperado: version, goal, files.")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ProposalError("Versão inválida.")
    if not isinstance(data["goal"], str) or not 1 <= len(data["goal"].strip()) <= 600:
        raise ProposalError("Objetivo ausente ou grande demais.")
    files = data["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ProposalError("O limite é de 1 a 20 arquivos.")
    total = 0
    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "content"}:
            raise ProposalError("Cada arquivo exige somente path e content.")
        path = validate_path(item["path"])
        name_key = str(path).casefold()
        if name_key in seen:
            raise ProposalError("Caminhos duplicados ou com colisão de maiúsculas.")
        seen.add(name_key)
        source = item["content"]
        if not isinstance(source, str) or not source.strip():
            raise ProposalError("Conteúdo ausente.")
        size = len(source.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise ProposalError("Arquivo excede 48 KB.")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ProposalError("Projeto excede 250 KB.")
        normalized.append({"path": str(path), "content": source})
    return {"version": 1, "goal": data["goal"].strip(), "files": normalized}


def review_proposal(data: dict[str, Any]) -> dict[str, Any]:
    """Source-level diagnostics are hints, NOT proof of security or design."""
    data = parse_proposal(json.dumps(data, ensure_ascii=False))
    diagnostics: list[dict[str, Any]] = []
    for item in data["files"]:
        path, code = item["path"], item["content"]
        kind = PurePosixPath(path).suffix.lower()
        errors: list[str] = []
        hints: list[str] = []
        if kind == ".py":
            try:
                ast.parse(code, filename=path)
            except SyntaxError as exc:
                errors.append(f"Python inválido: {exc.msg}.")
        elif kind == ".json":
            try:
                json.loads(code)
            except ValueError:
                errors.append("JSON inválido.")
        elif kind == ".html":
            inspector = HTMLSignals()
            inspector.feed(code)
            if not inspector.has_lang:
                hints.append("Definir lang no elemento html.")
            if not inspector.has_viewport:
                hints.append("Adicionar meta viewport.")
            if not inspector.has_title:
                hints.append("Adicionar título da página.")
            if "main" not in inspector.tags:
                hints.append("Adicionar landmark main.")
        elif kind == ".css":
            for needle, hint in [
                ("@media", "Verificar responsividade e tamanhos pequenos."),
                (":focus-visible", "Oferecer indicador visível de foco."),
                ("prefers-reduced-motion", "Respeitar preferência por movimento reduzido."),
            ]:
                if needle not in code:
                    hints.append(hint)
        diagnostics.append({"path": path, "errors": errors, "suggestions": hints,
                            "bytes": len(code.encode("utf-8"))})
    errors = sum(len(row["errors"]) for row in diagnostics)
    return {
        "status": "BLOCKED" if errors else "READY_FOR_HUMAN_REVIEW",
        "goal": data["goal"],
        "file_count": len(diagnostics),
        "files": diagnostics,
        "syntax_errors": errors,
        "warning": "Revisão estática parcial. Não executou código, navegador ou IA.",
    }


def _verify_workspace(root: Path) -> None:
    """Fail closed for symlinks in root ancestry, existing target files or dirs."""
    if not root.is_absolute():
        raise ProposalError("Workspace precisa ser um caminho absoluto.")
    if not root.is_dir() or root.is_symlink():
        raise ProposalError("O workspace deve existir e ser um diretório real.")
    for ancestor in (root, *root.parents):
        if ancestor.is_symlink():
            raise ProposalError("Diretório simbólico não permitido no workspace.")


def apply_new_files(data: dict[str, Any], workspace: Path, *, approved: bool = False) -> list[str]:
    """Create only absent files, atomically with O_EXCL; rollback on failure.

    Explicit approval is required. Does NOT run code, install dependencies,
    open a browser, remove files, or overwrite existing project files.
    """
    if approved is not True:
        raise PermissionError("Use --approve após revisar os arquivos propostos.")
    data = parse_proposal(json.dumps(data, ensure_ascii=False))
    report = review_proposal(data)
    if report["status"] != "READY_FOR_HUMAN_REVIEW":
        raise ProposalError("A proposta possui erros de sintaxe bloqueantes.")
    root = Path(workspace)
    _verify_workspace(root)
    # Check before writes; no existing target files or symlink traversal.
    for item in data["files"]:
        path = root.joinpath(*PurePosixPath(item["path"]).parts)
        for parent in (path.parent, *list(path.parent.parents)):
            if parent == root:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ProposalError("Subdiretório protegido ou não confiável.")
        if path.exists() or path.is_symlink():
            raise ProposalError(f"Arquivo já existe, não será substituído: {item['path']}")
    created: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for item in data["files"]:
            target = root.joinpath(*PurePosixPath(item["path"]).parts)
            cursor = root
            for segment in PurePosixPath(item["path"]).parts[:-1]:
                cursor = cursor / segment
                if cursor.is_symlink():
                    raise ProposalError("Symlink detectado antes da escrita.")
                if not cursor.exists():
                    cursor.mkdir()
                    created_dirs.append(cursor)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(target, flags, 0o600)
            created.append(target)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(item["content"])
        return [item["path"] for item in data["files"]]
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
