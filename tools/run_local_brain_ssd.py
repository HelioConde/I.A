#!/usr/bin/env python3
"""Interactive Windows-native functional runner for the frozen Brain-SSD V0."""
from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.hud.server import create_server
from brain_ssd.hud.state import HudRuntime
from brain_ssd.local_runtime.pipeline import LocalBrainSSD, atomic_write_json
from brain_ssd.observability.replay import phase_catalog


def mib(value: int | float | None) -> str:
    return "N/D" if value is None else f"{value / 1024**2:.1f} MiB"


def print_result(result: dict[str, Any], technical: bool) -> None:
    print("\nResposta:\n")
    print(result["answer"])
    retrieval = result["retrieval"]
    generation = result["generation"]["metrics"]
    print(
        f"\n[Brain-SSD] {retrieval['status']} | páginas {retrieval['activated_pages']} | "
        f"contexto {retrieval['context']['estimated_tokens']} tokens | "
        f"Qwen {generation.get('latency_ms', 0):.0f} ms"
    )
    if technical:
        print(json.dumps({
            "environment_type": result["environment_type"],
            "phase4e_valid": result["phase4e_valid"],
            "timing_ms": result["timing_ms"],
            "bottleneck": result["bottleneck"],
            "working_set_max": mib(generation.get("working_set_bytes_max")),
            "private_bytes_max": mib(generation.get("private_bytes_max")),
            "cpu_percent_total_average": generation.get("cpu_percent_total_average"),
            "cpu_percent_total_peak": generation.get("cpu_percent_total_peak"),
            "process_read_transfer_bytes": generation.get("read_transfer_bytes_delta"),
            "physical_read_bytes": generation.get("physical_read_bytes"),
        }, ensure_ascii=False, indent=2))


def print_status(runtime: LocalBrainSSD, smoke: dict[str, Any]) -> None:
    print(json.dumps({
        "environment_type": runtime.capabilities.environment_type,
        "development_status": "EXPERIMENTAL_FUNCTIONAL_RUNTIME",
        "phase4e_valid": False,
        "phase4e_invalid_reason": runtime.capabilities.phase4e_invalid_reason,
        "smoke_tests": smoke["status"],
        "model": str(runtime.model_path),
        "runtime": str(runtime.executable),
    }, ensure_ascii=False, indent=2))


def show_help() -> None:
    print("Comandos: /status, /metrics, /brain, /sources, /clear, /help, /quit")


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute Brain-SSD V0 locally with Qwen CPU-only")
    parser.add_argument("--query", help="Run one query and exit")
    parser.add_argument("--technical", action="store_true", help="Show technical metrics after each answer")
    parser.add_argument("--hud", action="store_true", help="Start the existing live HUD in this process")
    parser.add_argument("--hud-port", type=int, default=8765)
    parser.add_argument("--no-open-browser", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip startup smoke tests after a prior successful run")
    parser.add_argument("--runtime", type=Path, help="Explicit llama-completion executable")
    parser.add_argument("--core-mode", choices=("subprocess", "persistent"), default="subprocess", help="Core lifecycle; persistent is experimental and opt-in")
    parser.add_argument("--persistent-runtime", type=Path, help="Explicit experimental llama-server executable")
    args = parser.parse_args()

    hud_runtime: HudRuntime | None = None
    server = None
    if args.hud:
        hud_runtime = HudRuntime()
        hud_runtime.state.reset(data_source="WINDOWS NATIVE LIVE", demo_data=False, phases=phase_catalog(ROOT))
        server = create_server(hud_runtime, ROOT / "hud", "127.0.0.1", args.hud_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        print(f"HUD ao vivo: {url}")
        if not args.no_open_browser:
            webbrowser.open(url)

    try:
        with LocalBrainSSD(
            ROOT,
            executable=args.runtime,
            core_mode=args.core_mode,
            persistent_executable=args.persistent_runtime,
        ) as runtime:
            print("Brain-SSD V0 — Windows Native Functional")
            print(f"CPU-only | Qwen3-0.6B Q8_0 | Core {runtime.core_mode} | fase4e_valid=false")
            audit = runtime.startup_audit()
            if not audit["runtime"]["frozen_commit_match"] or not audit["runtime"]["cpu_only_build"]:
                raise RuntimeError("The llama.cpp runtime does not match the frozen CPU-only build.")
            if args.skip_smoke:
                smoke_path = runtime.results_dir / "smoke-tests.json"
                if not smoke_path.is_file():
                    raise FileNotFoundError("--skip-smoke requires an existing results/windows_native/smoke-tests.json")
                smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
                if smoke.get("status") != "PASS":
                    raise RuntimeError("The prior smoke suite did not pass.")
            else:
                print("Executando smoke tests (mmap, retrieval e Qwen CPU)...")
                smoke = runtime.run_smoke_suite()
                if smoke["status"] != "PASS":
                    raise RuntimeError("Startup smoke tests failed; see results/windows_native/smoke-tests.json")
                print("Smoke tests: PASS")

            last: dict[str, Any] | None = None

            def execute(query: str) -> dict[str, Any]:
                nonlocal last
                last = runtime.answer(query, hud_runtime=hud_runtime)
                first_path = runtime.results_dir / "first-end-to-end.json"
                if not first_path.is_file():
                    atomic_write_json(first_path, last)
                print_result(last, args.technical)
                return last

            if args.query:
                execute(args.query)
                return 0

            print("\nDigite uma pergunta técnica. Use /help para ver os comandos.")
            while True:
                try:
                    query = input("\nbrain-ssd> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nEncerrando com segurança.")
                    break
                if not query:
                    continue
                command = query.casefold()
                if command in {"/quit", "/exit"}:
                    break
                if command == "/help":
                    show_help()
                elif command == "/clear":
                    print("\033[2J\033[H", end="")
                elif command == "/status":
                    print_status(runtime, smoke)
                elif command == "/metrics":
                    print(json.dumps(last["generation"]["metrics"] if last else {"status": "NO_RUN"}, ensure_ascii=False, indent=2))
                elif command == "/brain":
                    print(json.dumps(last["retrieval"] if last else {"status": "NO_RUN"}, ensure_ascii=False, indent=2))
                elif command == "/sources":
                    print(json.dumps(last["retrieval"]["sources"] if last else [], ensure_ascii=False, indent=2))
                else:
                    execute(query)
        return 0
    except KeyboardInterrupt:
        print("\nExecução interrompida; o processo filho foi encerrado.")
        return 130
    except Exception as error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 1
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if hud_runtime is not None:
            hud_runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
