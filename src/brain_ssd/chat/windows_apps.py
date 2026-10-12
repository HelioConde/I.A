"""Windows application inventory and process snapshot (read-only, local).

No WMI Win32_Product (MSI repair side effects), shell or arbitrary commands.
Installed-app discovery is incomplete by design: registry registration is optional.
"""
from __future__ import annotations

import csv
import ctypes
import io
import os
import subprocess
from pathlib import Path
from typing import Any

_MAX_SCANNED = 6000
_MAX_ITEMS = 30


def _system_dir() -> Path:
    """Use the Windows API instead of trusting mutable SystemRoot/PATH values."""
    if os.name != "nt":
        raise OSError("Sistema Windows necessário.")
    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if not length or length >= len(buffer):
        raise OSError("Não foi possível localizar System32.")
    return Path(buffer.value)


def _filter(items: list[dict[str, Any]], name: str | None, limit: int = _MAX_ITEMS) -> dict[str, Any]:
    query = (name or "").casefold().strip()
    if query:
        items = [row for row in items if query in row["name"].casefold()]
    ordered = sorted(items, key=lambda row: row["name"].casefold())
    return {"items": ordered[:limit], "total_matches": len(ordered),
            "truncated": len(ordered) > limit,
            "query": name or ""}


def installed_apps(name: str | None = None) -> dict[str, Any]:
    """Read HKCU/HKLM Uninstall entries, both registry views when available."""
    if os.name != "nt":
        raise OSError("Inventário de aplicativos disponível somente no Windows.")
    import winreg

    subkey = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    seen: set[tuple[str, str]] = set()
    results: list[dict[str, Any]] = []

    def get(key: Any, value: str) -> str:
        try:
            val, _ = winreg.QueryValueEx(key, value)
            return val.strip() if isinstance(val, str) else str(val) if isinstance(val, int) else ""
        except OSError:
            return ""

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                root = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            with root:
                try:
                    count = min(winreg.QueryInfoKey(root)[0], _MAX_SCANNED)
                except OSError:
                    continue
                for i in range(count):
                    try:
                        child_name = winreg.EnumKey(root, i)
                        child = winreg.OpenKey(root, child_name)
                    except OSError:
                        continue
                    with child:
                        display = get(child, "DisplayName")
                        if not display or len(display) > 180 or get(child, "SystemComponent") == "1":
                            continue
                        version = get(child, "DisplayVersion")[:80]
                        signature = (display.casefold(), version.casefold())
                        if signature in seen:
                            continue
                        seen.add(signature)
                        results.append({
                            "name": display, "version": version,
                            "publisher": get(child, "Publisher")[:100],
                        })
    response = _filter(results, name)
    response["source"] = "Windows Registry HKCU/HKLM Uninstall (32/64-bit)"
    response["notice"] = "Registro pode omitir aplicativos portáteis, MSIX e instalações sem registro."
    return response


def running_apps(name: str | None = None) -> dict[str, Any]:
    """Process executable names/PIDs, never command lines or environment values.

    psutil is optional; otherwise use the standard tasklist executable.
    """
    if os.name != "nt":
        raise OSError("Inventário de processos disponível somente no Windows.")
    rows: list[dict[str, Any]] = []
    method = "tasklist.exe"
    try:
        import psutil  # type: ignore
    except ImportError:
        pass
    else:
        method = "psutil (process name and PID only)"
        for process in psutil.process_iter(["name", "pid"]):
            try:
                info = process.info
                name_ = info.get("name")
                if isinstance(name_, str) and name_:
                    rows.append({"name": name_[:180], "pid": int(info["pid"])})
            except (psutil.Error, OSError, ValueError, TypeError):
                continue
    if method == "tasklist.exe":
        # Fixed binary, no user-controlled args and never shell=True.
        tasklist = _system_dir() / "tasklist.exe"
        if not tasklist.is_file():
            raise OSError("tasklist.exe não encontrado.")
        completed = subprocess.run([str(tasklist), "/FO", "CSV", "/NH"],
                                   capture_output=True, timeout=15, check=False)
        if completed.returncode != 0:
            raise OSError("Falha ao consultar processos do Windows.")
        # Tasklist CSV is emitted in the active Windows OEM/ANSI code page.
        import locale
        decoded = completed.stdout.decode(locale.getpreferredencoding(False),
                                          errors="replace")
        for row in csv.reader(io.StringIO(decoded)):
            if len(row) < 2:
                continue
            try:
                pid = int(row[1].replace(",", "").strip())
            except ValueError:
                continue
            if row[0].strip():
                rows.append({"name": row[0].strip()[:180], "pid": pid})
    rows = list({(p["pid"], p["name"].casefold()): p
                 for p in rows if isinstance(p.get("pid"), int)}.values())
    result = _filter(rows, name)
    result["source"] = method
    result["notice"] = ("Processos não são equivalentes às janelas visíveis. "
                        "Alguns processos protegidos podem estar ausentes.")
    return result


LAUNCH_TARGETS = {
    "notepad": ("Bloco de Notas", "notepad.exe"),
    "calculator": ("Calculadora", "calc.exe"),
}


def run_approved_app(app_id: str) -> dict[str, Any]:
    """Start one of two fixed Windows applications, no arguments or shell."""
    if os.name != "nt":
        raise OSError("Abertura de aplicativos disponível somente no Windows.")
    target = LAUNCH_TARGETS.get(app_id)
    if target is None:
        raise ValueError("Aplicativo não autorizado.")
    label, exe = target
    system_dir = _system_dir()
    full_path = system_dir / exe
    if not full_path.is_file():
        raise OSError("Aplicativo não encontrado no Windows.")
    # No execution of arbitrary paths, documents, arguments, or commands.
    child = subprocess.Popen([str(full_path)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             cwd=str(system_dir), shell=False)
    return {"app_id": app_id, "label": label, "started_pid": child.pid,
            "status": "requested", "notice": "Processo iniciado; abertura da janela não verificada."}


# Registered Start Menu entries are launchable apps; Uninstall entries are not.
def _normalized_app_name(value: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(c for c in name if not unicodedata.combining(c)).split())


_DENIED_LAUNCH_NAMES = frozenset({
    "powershell", "windows powershell", "powershell ise", "pwsh",
    "prompt de comando", "command prompt", "cmd", "windows terminal",
    "terminal", "regedit", "editor do registro", "registry editor",
    "task scheduler", "agendador de tarefas", "gerenciamento do computador",
    "computer management", "windows security", "seguranca do windows",
    "gerenciador de tarefas", "task manager", "control panel",
    "painel de controle", "windows tools", "ferramentas do windows",
    "executar", "run", "diskpart", "explorer", "explorador de arquivos",
    "file explorer", "command processor", "editor de politica de grupo",
})


def start_menu_apps(name: str | None = None) -> dict[str, Any]:
    """Return real launchable Start Menu app registrations, not paths or scripts."""
    if os.name != "nt":
        raise OSError("Menu Iniciar disponível somente no Windows.")
    ps = _system_dir() / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not ps.is_file():
        raise OSError("PowerShell do Windows indisponível para consulta.")
    # This script is constant; app names are filtered in Python, never in shell.
    command = ("Get-StartApps | Select-Object Name,AppID | "
               "ConvertTo-Json -Compress -Depth 3")
    completed = subprocess.run(
        [str(ps), "-NoLogo", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Restricted", "-Command", command],
        capture_output=True, timeout=18, check=False,
    )
    if completed.returncode:
        raise OSError("Consulta do menu Iniciar falhou.")
    import json
    try:
        data = completed.stdout.decode("utf-8-sig", errors="replace").strip()
        raw = json.loads(data) if data else []
    except ValueError:
        raise OSError("Catálogo do menu Iniciar inválido.") from None
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise OSError("Catálogo do menu Iniciar inválido.")
    import re
    rows, seen = [], set()
    for item in raw[:_MAX_SCANNED]:
        if not isinstance(item, dict):
            continue
        label, app_id = item.get("Name"), item.get("AppID")
        if not isinstance(label, str) or not isinstance(app_id, str):
            continue
        label, app_id = label.strip(), app_id.strip()
        if not label or len(label) > 180 or not 4 <= len(app_id) <= 300:
            continue
        if not re.fullmatch(r"[A-Za-z0-9._{}!\\-]+", app_id):
            continue
        identity = (label.casefold(), app_id)
        if identity in seen:
            continue
        seen.add(identity)
        rows.append({"name": label, "app_id": app_id})
    result = _filter(rows, name, limit=600)
    result["source"] = "Windows Get-StartApps (Menu Iniciar)"
    result["notice"] = (
        "Somente aplicativos registrados no menu Iniciar; portáteis ou sem "
        "atalho podem estar ausentes. Não equivale a todos os executáveis no disco."
    )
    return result


def run_start_app(app_name: str) -> dict[str, Any]:
    """Run one uniquely identified Start app, never an arbitrary user command."""
    if os.name != "nt":
        raise OSError("Abertura direta disponível somente no Windows.")
    if not isinstance(app_name, str) or not 2 <= len(app_name.strip()) <= 100:
        raise ValueError("Nome de aplicativo inválido.")
    if any(x in app_name for x in ("/", chr(92), ":", "|", "&", ";", "$", chr(96), "\n", "\r")):
        raise ValueError("Comandos e caminhos não são nomes de aplicativos.")
    query = _normalized_app_name(app_name)
    aliases = {
        "notepad": ("notepad", "bloco de notas"),
        "bloco de notas": ("bloco de notas", "notepad"),
        "calculator": ("calculator", "calculadora"),
        "calculadora": ("calculadora", "calculator"),
    }
    candidates = aliases.get(query, (query,))
    if query in _DENIED_LAUNCH_NAMES:
        raise ValueError("Aplicativo administrativo ou interpretador de comandos bloqueado.")
    inventory = start_menu_apps()
    rows = inventory["items"]
    exact = [entry for entry in rows if _normalized_app_name(entry["name"]) in candidates]
    if not exact and len(query) >= 4:
        exact = [entry for entry in rows if query in _normalized_app_name(entry["name"])]
    if not exact:
        raise ValueError("Aplicativo não localizado no menu Iniciar.")
    if len(exact) != 1:
        raise ValueError("Nome ambíguo; informe o nome completo do aplicativo.")
    item = exact[0]
    if _normalized_app_name(item["name"]) in _DENIED_LAUNCH_NAMES:
        raise ValueError("Aplicativo administrativo ou interpretador de comandos bloqueado.")
    import re
    app_id = item["app_id"]
    if not isinstance(app_id, str) or not re.fullmatch(r"[A-Za-z0-9._{}!\\-]+", app_id):
        raise ValueError("Identificador de aplicativo inválido.")
    explorer = _system_dir().parent / "explorer.exe"
    if not explorer.is_file():
        raise OSError("Windows Explorer indisponível.")
    child = subprocess.Popen(
        [str(explorer), "shell:AppsFolder" + chr(92) + app_id],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, cwd=str(explorer.parent), shell=False,
    )
    return {"label": item["name"], "app_id": app_id,
            "started_pid": child.pid, "status": "requested",
            "notice": "Solicitação enviada ao Explorer; janela não verificada."}
