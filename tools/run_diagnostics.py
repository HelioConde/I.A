#!/usr/bin/env python3
"""Run Brain-SSD regression tests and collect *safe metadata only*.

CLI examples:
  python tools/run_diagnostics.py
  python tools/run_diagnostics.py --core
  python tools/run_diagnostics.py --real-windows
  python tools/run_diagnostics.py --ci

The test program output can be shown in terminal using --verbose but is NEVER
copied into the event files, manifests or ZIP (it might reveal private data).
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.diagnostics import DiagnosticLogger, default_diagnostics_dir, export_diagnostics, machine_metadata

CHAT_SUITES = [
    ("chat_windows", "test_chat_windows.py"),
    ("chat_history", "test_chat_history.py"),
    ("chat_stream", "test_chat_stream.py"),
    ("chat_doctor", "test_chat_doctor.py"),
    ("chat_episodic", "test_chat_episodic.py"),
    ("chat_episodic_http", "test_chat_episodic_http.py"),
    ("cognitive_lab", "test_cognitive_lab.py"),
    ("consolidation", "test_consolidation.py"),
    ("diagnostics", "test_diagnostics.py"),
    ("compare_diagnostics", "test_compare_diagnostics.py"),
]
CORE_SUITES = [
    ("core", "test_core.py"),
    ("storage", "test_storage.py"),
    ("router_gating", "test_router_gating.py"),
    ("cache_policy", "test_cache_policy.py"),
    ("hybrid", "test_hybrid.py"),
    ("progressive", "test_progressive.py"),
]
LAB_TOOLS = [
    ("bench_episodic_memory", "tools/bench_episodic_memory.py"),
    ("run_cognitive_lab", "tools/run_cognitive_lab.py"),
]


def execute_command(argv: list[str], label: str, logger: DiagnosticLogger,
                    *, timeout: int, verbose: bool) -> bool:
    started = time.perf_counter()
    logger.emit("test.start", suite=label, status="READY")
    try:
        proc = subprocess.run(
            argv, cwd=ROOT, timeout=timeout, capture_output=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, errors="replace",
            check=False,
        )
        passed = proc.returncode == 0
        if verbose:
            # Explicitly terminal-only; do not persist potentially sensitive test output.
            print((proc.stdout + proc.stderr)[-10_000:])
        logger.emit("test.result", suite=label,
                    status="PASS" if passed else "FAIL",
                    exit_code=proc.returncode,
                    duration_ms=(time.perf_counter() - started) * 1000)
        print(("[OK] " if passed else "[FALHOU] ") + label)
        return passed
    except subprocess.TimeoutExpired:
        logger.emit("test.error", suite=label, status="ERROR",
                    error_type="TimeoutError", duration_ms=(time.perf_counter()-started)*1000)
        print("[TIMEOUT] " + label)
        return False
    except OSError as exc:
        logger.emit("test.error", suite=label, status="ERROR",
                    error_type=type(exc).__name__,
                    duration_ms=(time.perf_counter()-started)*1000)
        print("[FALHA AO EXECUTAR] " + label)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain-SSD — teste com trilha de diagnóstico segura")
    parser.add_argument("--core", action="store_true", help="Executa também regressão do núcleo SSD")
    parser.add_argument("--real-windows", action="store_true",
                        help="Testa Qwen/llama.cpp reais se o Windows já estiver configurado")
    parser.add_argument("--ci", action="store_true",
                        help="Usa pasta isolada no CI e cria pacote para artifacts")
    parser.add_argument("--logs-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--verbose", action="store_true",
                        help="Exibe saída bruta APENAS no terminal (não no ZIP)")
    args=parser.parse_args()
    directory = args.logs_dir or (ROOT / "results" / "diagnostics" / "ci" if args.ci
                                   else default_diagnostics_dir())
    logger=DiagnosticLogger(directory)
    logger.emit("session.start", **machine_metadata(),
                git_sha=os.environ.get("GITHUB_SHA", ""),
                profile="not_applicable", core_mode="not_applicable")
    suites=CHAT_SUITES + ([("chat_runtime", "test_chat_runtime.py")] if os.name=="nt" else [])
    if args.core:
        suites += CORE_SUITES
    results=[]
    try:
        for label, filename in suites:
            results.append(execute_command(
                [sys.executable, "-m", "unittest", "discover",
                 "-s", "tests", "-p", filename, "-v"],
                label, logger, timeout=180, verbose=args.verbose
            ))
        for label, filename in LAB_TOOLS:
            results.append(execute_command(
                [sys.executable, filename], label, logger,
                timeout=180, verbose=args.verbose
            ))
        if args.real_windows:
            results.append(execute_command(
                [sys.executable, "tools/validate_chat_windows.py",
                 "--profile", "economia", "--diagnostics-dir", str(directory)],
                "real_windows_inference", logger, timeout=240, verbose=args.verbose
            ))
    finally:
        logger.emit("session.stop", status="PASS" if all(results) and results else "FAIL")
        target=args.output or (
            directory / "brain-ssd-ci-diagnostics.zip" if args.ci
            else default_diagnostics_dir().parent / "exports" / "brain-ssd-latest-diagnostics.zip"
        )
        summary=export_diagnostics(directory,target)
        print("Log local:", directory.resolve())
        print("Pacote seguro para revisão:", target.resolve())
        print("Resumo de eventos:", json.dumps(summary["event_counts"], ensure_ascii=False))
        print("Nenhum dado foi enviado para nenhum serviço.")
    return 0 if results and all(results) else 1


if __name__=="__main__":
    raise SystemExit(main())
