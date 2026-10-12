"""A small, deterministic, read-only agent orchestrator for Brain-SSD.

An investigation is explicitly planned and accepted before any local tools are
called.  It never executes model-generated tool calls, source code, shell,
subprocesses, patch writes or application launches. A report distinguishes
verified tool evidence from suggestions and missing information.

The first iteration supports four bounded workflows. Natural-language model
planning and multi-file editing are future work, not implied by this module.
"""
from __future__ import annotations

import secrets
import threading
import time
from pathlib import Path
from typing import Any

from brain_ssd.chat.copilot import CopilotPermissionError

_PLAN_TTL = 90
_MAX_ERROR = 4000
_MAX_FILE_NAME = 1200
_TASKS = {
    "godot_overview": (
        ("Confirmar pasta autorizada e projeto Godot", "copilot_file_scope"),
        ("Consultar scripts, cenas e recursos", "godot_project_inspector"),
        ("Apresentar achados e limites", "evidence_summary"),
    ),
    "godot_diagnosis": (
        ("Confirmar projeto Godot e mensagem de erro", "copilot_file_scope"),
        ("Inspecionar a estrutura do projeto", "godot_project_inspector"),
        ("Confrontar a mensagem com os arquivos e linhas reais", "godot_error_inspector"),
        ("Sugerir próximos passos sem alterar arquivos", "evidence_summary"),
    ),
    "code_review": (
        ("Confirmar arquivo dentro das pastas autorizadas", "copilot_file_scope"),
        ("Executar inspeção estática limitada de código", "code_inspector"),
        ("Apresentar observações e limites", "evidence_summary"),
    ),
    "pc_report": (
        ("Consultar fatos atuais do sistema operacional", "windows_system_info"),
        ("Apresentar recomendações limitadas pelas métricas obtidas", "evidence_summary"),
    ),
}


class LocalAgentCore:
    """Per-session one-use investigation planner, no execution authority."""

    def __init__(self, copilot: Any):
        self.copilot = copilot
        self._pending: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()

    def prepare(
        self,
        task: object,
        *,
        project: object = None,
        error: object = None,
        path: object = None,
    ) -> dict[str, Any]:
        if not self.copilot.status().get("enabled"):
            raise CopilotPermissionError("Copiloto local não autorizado nesta sessão.")
        if not isinstance(task, str) or task not in _TASKS:
            raise CopilotPermissionError("Tipo de investigação não autorizado.")
        params: dict[str, str] = {}
        if task in ("godot_overview", "godot_diagnosis"):
            if not isinstance(project, str) or len(project) > _MAX_FILE_NAME:
                raise CopilotPermissionError("Informe a pasta do projeto.")
            root = self.copilot._godot_inspector()._project_path(project)
            params["project"] = str(root)
            if task == "godot_diagnosis":
                if (not isinstance(error, str)
                        or not 0 < len(error.strip()) <= _MAX_ERROR):
                    raise CopilotPermissionError(
                        "Cole o erro real do Godot com até 4.000 caracteres.")
                params["error"] = error.strip()
        elif task == "code_review":
            if not isinstance(path, str) or len(path) > _MAX_FILE_NAME:
                raise CopilotPermissionError("Selecione um arquivo de código.")
            selected = self.copilot._path(path)
            if selected.suffix.casefold() not in (
                ".gd", ".py", ".js", ".jsx", ".ts", ".tsx", ".cs",
                ".css", ".html", ".json", ".md", ".toml", ".yaml", ".yml",
            ):
                raise CopilotPermissionError("Este arquivo não pode ser inspecionado.")
            if not selected.is_file():
                raise CopilotPermissionError("Arquivo não encontrado.")
            params["path"] = str(selected)
        # pc_report never inspects local project files or runs apps.
        proposal_id = secrets.token_urlsafe(32)
        expires = time.monotonic() + _PLAN_TTL
        with self._lock:
            # Deliberate: at most one investigation proposal per session.
            self._pending.clear()
            self._pending[proposal_id] = {
                "task": task, "params": params, "expires": expires,
            }
        # The error itself is intentionally excluded from the plan preview.
        # It may contain secrets in stacktraces/logs; it remains in RAM only.
        return {
            "token": proposal_id,
            "task": task,
            "scope": {k: v for k, v in params.items() if k != "error"},
            "steps": [
                {"number": index, "title": title, "tool": source}
                for index, (title, source) in enumerate(_TASKS[task], 1)
            ],
            "risk": "Leitura local limitada; nenhuma modificação ou execução externa.",
            "expires_seconds": _PLAN_TTL,
            "notice": (
                "Plano determinístico, não raciocínio autônomo do modelo. "
                "Nenhuma ferramenta de investigação foi executada ainda."
            ),
        }

    def execute(self, token: object) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 200:
            raise CopilotPermissionError("Identificador do plano inválido.")
        with self._lock:
            pending = self._pending.pop(token, None)
        if pending is None or time.monotonic() > pending["expires"]:
            raise CopilotPermissionError(
                "Plano expirado ou já usado. Prepare uma nova investigação.")
        if not self._run_lock.acquire(blocking=False):
            raise CopilotPermissionError("Outra investigação está em andamento.")
        try:
            task = pending["task"]
            params = pending["params"]
            return self._execute_authorized(task, params)
        finally:
            self._run_lock.release()

    def _execute_authorized(self, task: str, params: dict[str, str]) -> dict[str, Any]:
        evidence: list[dict[str, Any]] = []
        suggestions: list[str] = []
        status = "completed"
        if task in ("godot_overview", "godot_diagnosis"):
            project = self.copilot.inspect_godot_project(params["project"])
            evidence.append({
                "step": "godot_project_inspector",
                "source": "project.godot e arquivos autorizados no disco",
                "facts": {
                    "root": project["project_root"],
                    "scripts": project["script_count"],
                    "scenes": project["scene_count"],
                    "resources": project["resources_count"],
                    "scanned_entries": project["scanned_entries"],
                    "truncated": project["truncated"],
                    "todos": project["todo"][:6],
                },
            })
            if project["truncated"]:
                status = "partial"
                suggestions.append(
                    "A busca atingiu um limite; examine uma pasta/projeto menor.")
            if task == "godot_diagnosis":
                report = self.copilot.diagnose_godot_error(
                    params["project"], params["error"])
                evidence.append({
                    "step": "godot_error_inspector",
                    "source": "mensagem fornecida e correspondência com arquivos existentes",
                    "facts": {
                        "matched_count": report["matched_count"],
                        "matches": report["matches"][:4],
                        "truncated": report["truncated"],
                    },
                })
                suggestions.extend(report["recommendations"][:5])
                if not report["matched_count"] or report["truncated"]:
                    status = "partial"
            else:
                suggestions.extend(project["recommendations"][:4])
        elif task == "code_review":
            report = self.copilot.review_code(params["path"])
            evidence.append({
                "step": "code_inspector",
                "source": "arquivo autorizado UTF-8",
                "facts": {
                    "path": report["path"],
                    "line_count": report["line_count"],
                    "bytes": report["size_bytes"],
                    "warnings": report["warnings"][:8],
                    "todos": report["todos"][:8],
                },
            })
            suggestions.append(
                "Se quiser editar, prepare um diff em uma ação separada. "
                "Nenhuma correção foi criada ou aplicada por esta investigação."
            )
        elif task == "pc_report":
            report = self.copilot.system_info()
            evidence.append({
                "step": "windows_system_info",
                "source": "API do sistema operacional no momento da consulta",
                "facts": {
                    "os": report["os"],
                    "architecture": report["architecture"],
                    "cpu_name": report.get("cpu_name"),
                    "cpu_threads": report.get("cpu_threads"),
                    "ram_gib": report.get("ram_total_gib"),
                    "disks": report.get("disks", [])[:5],
                    "python": report["python"],
                },
            })
            ram = report.get("ram_total_gib")
            if isinstance(ram, (int, float)) and ram < 8:
                suggestions.append(
                    "Com menos de 8 GiB de RAM, mantenha poucos aplicativos "
                    "pesados abertos durante inferência local.")
            suggestions.append(
                "Latência da IA depende de modelo, CPU e uso atual; "
                "a consulta não mediu GPU, temperatura ou consumo por processo.")
        else:
            # Never invoke a dynamic tool or model-generated command.
            raise CopilotPermissionError("Investigação não disponível.")
        return {
            "task": task,
            "status": status,
            "evidence": evidence,
            "suggestions": suggestions[:8],
            "actions_taken": [
                "Consultas locais somente leitura; nenhuma aplicação iniciada, "
                "nenhum script executado e nenhum arquivo modificado."
            ],
            "next_step": (
                "Revise o relatório. Para alterações ou testes, utilize os "
                "controles independentes de confirmação e backup."
            ),
            "notice": (
                "Resultados de ferramentas locais não provam que um bug foi "
                "corrigido. Interpretações e recomendações não são fatos medidos."
            ),
        }
