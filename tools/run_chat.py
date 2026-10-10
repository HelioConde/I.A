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
from brain_ssd.local_runtime.pipeline import LocalBrainSSD


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain-SSD local Windows visual chat")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-open-browser", action="store_true")
    parser.add_argument("--core-mode", choices=("subprocess", "persistent"), default="subprocess")
    args = parser.parse_args()
    engine = ChatEngine(lambda: LocalBrainSSD(ROOT, core_mode=args.core_mode))
    try:
        server = create_chat_server(engine, ROOT / "chat", port=args.port)
    except OSError as exc:
        print(f"Não foi possível abrir a porta {args.port}: {exc}", file=sys.stderr)
        return 1
    threading.Thread(target=engine.start, name="brain-chat-initialize", daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Brain-SSD Chat local: {url}")
    print("CPU-only. Nenhuma chave de API ou conexão com serviço externo é necessária.")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
