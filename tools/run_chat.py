#!/usr/bin/env python3
"""Start the experimental Brain-SSD Windows chat UI with a real CPU-only local model."""
from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.server import ChatEngine, create_chat_server
from brain_ssd.chat.history import ChatHistory, default_history_path
from brain_ssd.chat.episodic import EpisodicMemory, default_episodic_path
from brain_ssd.chat.diagnostics import DiagnosticLogger, default_diagnostics_dir, machine_metadata
from brain_ssd.chat.runtime import LocalChatRuntime, PROFILES


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain-SSD local Windows visual chat")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--diagnostics-dir", type=Path, default=None, help="Diretório dos logs JSONL privados")
    parser.add_argument("--no-diagnostics", action="store_true", help="Desativa a telemetria local")
    parser.add_argument("--no-open-browser", action="store_true")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="economia")
    parser.add_argument("--cognitive-shadow", action="store_true", help="Mede atenção/memória de trabalho em shadow; sem alterar respostas")
    parser.add_argument("--memory-aliases", action="store_true", help="Sinônimos limitados PT-BR (experimental e opt-in; requer --episodic-memory)")
    parser.add_argument("--episodic-memory", action="store_true", help="Ativa memórias confirmadas pelo usuário; desativadas por padrão")
    parser.add_argument("--episodic-db", type=Path, default=None)
    parser.add_argument("--history-db", type=Path, default=None, help="Banco SQLite das conversas (local)")
    parser.add_argument("--core-mode", choices=("subprocess", "persistent"), default=None, help="Substitui o modo do perfil")
    args = parser.parse_args()
    if args.memory_aliases and not args.episodic_memory:
        parser.error("--memory-aliases requer --episodic-memory.")
    diagnostics = None if args.no_diagnostics else DiagnosticLogger(args.diagnostics_dir or default_diagnostics_dir())
    if diagnostics:
        diagnostics.emit("session.start", **machine_metadata(), profile=args.profile,
            core_mode=args.core_mode or PROFILES[args.profile]["mode"],
            cpu_threads=PROFILES[args.profile]["threads"],
            episodic_enabled=args.episodic_memory, shadow_enabled=args.cognitive_shadow)
    episodic_store = EpisodicMemory(args.episodic_db or default_episodic_path()) if args.episodic_memory else None
    engine = ChatEngine(lambda: LocalChatRuntime(ROOT, profile=args.profile, core_mode=args.core_mode), episodic_store=episodic_store, cognitive_shadow=args.cognitive_shadow, diagnostics=diagnostics, memory_aliases=args.memory_aliases,
        startup_reporter=lambda message: print("\n[Brain-SSD] " + message + "\n[Brain-SSD] Execute DIAGNOSTICAR-CHAT-WINDOWS.bat para verificar os requisitos.\n", file=sys.stderr, flush=True))
    history_store = ChatHistory(args.history_db or default_history_path())
    try:
        server = create_chat_server(engine, ROOT / "chat", port=args.port, history_store=history_store, episodic_store=episodic_store)
    except OSError as exc:
        print(f"Não foi possível abrir a porta {args.port}: {exc}", file=sys.stderr)
        return 1
    threading.Thread(target=engine.start, name="brain-chat-initialize", daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Brain-SSD Chat local: {url}")
    print(f"Perfil: {args.profile} | CPU-only | SSD opcional para conversar | sem API externa.")
    print(f"Histórico local privado: {history_store.path}")
    print(f"Memórias episódicas: {episodic_store.path if episodic_store else 'desativadas (opt-in --episodic-memory)'}")
    print(f"Diagnóstico estruturado: {diagnostics.path if diagnostics else 'desativado'}")
    print(f"Sinônimos episódicos: {'experimento ativo' if args.memory_aliases else 'desativados (padrão)'}")
    print(f"Estado/atenção cognitiva: {'SHADOW ativo (sem afetar resposta)' if args.cognitive_shadow else 'desativados'}")
    print("A primeira resposta pode levar mais tempo devido ao carregamento do modelo.")
    print("Mantenha o terminal aberto; pressione Ctrl+C para encerrar.")
    if not args.no_open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        engine.close()
        if diagnostics:
            diagnostics.emit("session.stop", status="OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
