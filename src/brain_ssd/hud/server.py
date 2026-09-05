from __future__ import annotations

import json
import mimetypes
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from brain_ssd.hud.state import HudRuntime
from brain_ssd.observability.snapshots import privacy_snapshot


@dataclass(frozen=True, slots=True)
class HudServerConfig:
    static_dir: Path
    hide_query: bool = False
    hide_records: bool = False
    hide_answer: bool = False


class HudHttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], runtime: HudRuntime, config: HudServerConfig) -> None:
        super().__init__(address, HudRequestHandler)
        self.runtime = runtime
        self.config = config

    def handle_error(self, request: Any, client_address: tuple[str, int]) -> None:
        # Browsers routinely reset an SSE/socket during reload or shutdown.
        # Observability must stay quiet and fail-open for those disconnects.
        return


class HudRequestHandler(BaseHTTPRequestHandler):
    server: HudHttpServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK, *, download: bool = False) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="brain-ssd-hud-snapshot.json"')
        self.end_headers()
        self.wfile.write(body)

    def _private_state(self) -> dict[str, Any]:
        config = self.server.config
        state = privacy_snapshot(
            self.server.runtime.state.snapshot(),
            hide_query=config.hide_query,
            hide_records=config.hide_records,
            hide_answer=config.hide_answer,
        )
        state["event_stream"] = {
            "latest_sequence": self.server.runtime.bus.latest_sequence,
            "dropped_events": self.server.runtime.bus.dropped_count,
        }
        return state

    def _serve_static(self, route: str) -> None:
        relative = "index.html" if route == "/" else route.lstrip("/")
        static_root = self.server.config.static_dir.resolve()
        candidate = (static_root / relative).resolve()
        try:
            candidate.relative_to(static_root)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_events(self, since: int) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        cursor = since
        try:
            while True:
                events = self.server.runtime.bus.wait_for_events(cursor, timeout_s=10.0)
                if not events:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                for event in events:
                    cursor = event.sequence
                    packet = f"id: {event.sequence}\nevent: brain-event\ndata: {event.to_json()}\n\n"
                    self.wfile.write(packet.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        route = parsed.path
        if route == "/api/health":
            self._send_json({"status": "ok", "service": "brain-ssd-hud", "time": time.time()})
        elif route == "/api/state":
            self._send_json(self._private_state())
        elif route == "/api/history":
            self._send_json({"history": self.server.runtime.state.history()})
        elif route == "/api/phases":
            self._send_json({"phases": self._private_state().get("phases", [])})
        elif route == "/api/export":
            self._send_json(self._private_state(), download=True)
        elif route == "/api/events":
            values = parse_qs(parsed.query).get("since", [self.headers.get("Last-Event-ID", "0")])
            try:
                since = max(0, int(values[0]))
            except (TypeError, ValueError):
                since = 0
            self._serve_events(since)
        elif route in {"/", "/app.js", "/styles.css"}:
            self._serve_static(route)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def create_server(
    runtime: HudRuntime,
    static_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    hide_query: bool = False,
    hide_records: bool = False,
    hide_answer: bool = False,
) -> HudHttpServer:
    config = HudServerConfig(
        static_dir=static_dir,
        hide_query=hide_query,
        hide_records=hide_records,
        hide_answer=hide_answer,
    )
    return HudHttpServer((host, port), runtime, config)
