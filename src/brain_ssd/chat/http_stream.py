"""Secure, local-only NDJSON-style SSE transport for actual chat tokens."""
from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any


def serve_stream(handler: Any, data: dict[str, Any]) -> None:
    """The host and Origin are verified in ChatHandler before dispatch."""
    engine = handler.server.engine
    store = handler.server.history_store
    request_id = data.get("request_id")
    conversation_id = data.get("conversation_id")
    question = data.get("message")
    if not isinstance(question, str) or not question.strip() or len(question.strip()) > 2000:
        raise ValueError("Digite uma mensagem de até 2.000 caracteres.")
    if conversation_id is not None and store is not None:
        # Validate the saved conversation before sending SSE response headers.
        history = store.recent_context(conversation_id)
    else:
        history = data.get("history", [])
    cancelled = engine.begin_stream(request_id)

    def event(name: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        handler.wfile.write(f"event: {name}\ndata: {encoded}\n\n".encode("utf-8"))
        handler.wfile.flush()

    try:
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache, no-transform")
        handler.send_header("X-Accel-Buffering", "no")
        handler.send_header("Connection", "close")
        handler.close_connection = True
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.end_headers()
        event("started", {"request_id": request_id})
        result = engine.ask(
            question, history,
            on_chunk=lambda text: event("delta", {"text": text}),
            cancel_event=cancelled,
            request_id=request_id,
            web_search=data.get("web_search", False),
            remember_web=data.get("remember_web", False),
            fast_web=data.get("fast_web", False),
            response_tokens=data.get("response_tokens"),
        )
        if cancelled.is_set():
            from brain_ssd.chat.streaming import GenerationCancelled
            raise GenerationCancelled()
        if conversation_id is not None and store is not None:
            store.append_exchange(conversation_id, question.strip(), result["answer"])
            result["conversation_id"] = conversation_id
        event("done", result)
    except Exception as exc:
        from brain_ssd.chat.streaming import GenerationCancelled
        if isinstance(exc, GenerationCancelled):
            try:
                event("cancelled", {"message": "Resposta interrompida e não salva."})
            except OSError:
                pass
        elif isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError)):
            cancelled.set()
        else:
            try:
                # Never stream arbitrary backend exception messages to the UI.
                if isinstance(exc, (RuntimeError, TimeoutError)):
                    event("error", {
                        "error": "O modelo local falhou ao gerar esta resposta. "
                                 "Verifique o diagnóstico com: "
                                 "py -3 tools/validate_chat_windows.py --profile economia. "
                                 "Consulte os logs locais se o problema persistir.",
                        "error_code": "MODEL_GENERATION_FAILED",
                    })
                else:
                    event("error", {
                        "error": "Falha interna no chat local. "
                                 "Consulte o diagnóstico antes de tentar novamente.",
                        "error_code": "LOCAL_CHAT_ERROR",
                    })
            except OSError:
                cancelled.set()
    finally:
        engine.finish_stream(request_id)
