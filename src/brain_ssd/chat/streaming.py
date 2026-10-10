"""Noncanonical chat-only token streaming and safe model cancellation."""
from __future__ import annotations

import codecs
from collections import deque
import json
import os
import subprocess
import threading
import time
import urllib.request
from typing import Any, Callable

from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.core_backend import PersistentCoreBackend, SubprocessPerQueryCore
from brain_ssd.local_runtime.windows_metrics import windows_process_snapshot, _perf_number


class GenerationCancelled(Exception):
    """A user cancelled a generation; no partial answer must be persisted."""


def _stop(process: Any) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _max_ram(samples: list[Any], key: str) -> int | None:
    values = [getattr(s, key, None) for s in samples]
    return max((x for x in values if x is not None), default=None)


def _subprocess_stream(core: SubprocessPerQueryCore, request: GenerationRequest,
                       on_chunk: Callable[[str], None], cancel: threading.Event) -> dict:
    started = time.monotonic()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    p = subprocess.Popen(list(core.backend.command(request)),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=0, creationflags=flags,
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    done = threading.Event()
    # Bounded tails: native stderr may be verbose during long model load.
    samples: deque[Any] = deque(maxlen=4096)
    stderr: deque[bytes] = deque(maxlen=64)
    output: list[str] = []
    first_at: float | None = None

    def read_stderr() -> None:
        if p.stderr is not None:
            for part in iter(lambda: p.stderr.read(4096), b""):
                stderr.append(part)

    def watch() -> None:
        while not done.wait(0.04):
            if cancel.is_set():
                _stop(p)
                return
            if os.name == "nt":
                # Telemetry is best-effort: sampling must never disable
                # cancellation, even if a child exits during Win32 polling.
                try:
                    if p.poll() is None:
                        samples.append(windows_process_snapshot(p.pid))
                except (OSError, AttributeError, ValueError):
                    pass

    thread_err = threading.Thread(target=read_stderr, daemon=True)
    thread_stop = threading.Thread(target=watch, daemon=True)
    thread_err.start()
    thread_stop.start()
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    try:
        if p.stdout is None:
            raise RuntimeError("Canal de saída do llama.cpp indisponível.")
        # Unbuffered pipe; read1/read returns as the native CLI flushes output.
        while True:
            if cancel.is_set():
                raise GenerationCancelled()
            part = p.stdout.read(256)
            if not part:
                break
            text = decoder.decode(part)
            if text:
                if first_at is None:
                    first_at = time.monotonic()
                output.append(text)
                on_chunk(text)
        tail = decoder.decode(b"", final=True)
        if tail:
            output.append(tail)
            on_chunk(tail)
        p.wait()
        if cancel.is_set():
            raise GenerationCancelled()
        err = b"".join(stderr).decode("utf-8", "replace")
        if p.returncode != 0:
            raise RuntimeError("llama.cpp falhou: " + err[-450:])
        core.model_loads += 1
        core.query_count += 1
        return {"return_code": 0, "stdout": "".join(output), "metrics": {
            "latency_ms": (time.monotonic() - started) * 1000,
            "ttft_ms": (first_at - started) * 1000 if first_at else None,
            "tokens_per_second": _perf_number(err, "eval time"),
            "working_set_bytes_max": _max_ram(samples, "working_set_bytes"),
            "private_bytes_max": _max_ram(samples, "private_bytes"),
            "physical_read_bytes": None,
        }}
    finally:
        done.set()
        _stop(p)
        thread_stop.join(timeout=3)
        thread_err.join(timeout=3)
        if p.stdout:
            p.stdout.close()
        if p.stderr:
            p.stderr.close()


def _persistent_stream(core: PersistentCoreBackend, request: GenerationRequest,
                       on_chunk: Callable[[str], None], cancel: threading.Event) -> dict:
    started = time.monotonic()
    done = threading.Event()
    first_at: float | None = None
    output: list[str] = []
    samples: deque[Any] = deque(maxlen=4096)
    timings: dict = {}

    def watch() -> None:
        while not done.wait(0.05):
            if cancel.is_set():
                # PersistentCoreBackend.start() holds its own RLock while
                # waiting for the model. Calling close() alone can block up
                # to ready_timeout_s. Terminate the child *before* close().
                active = core.process
                if active is not None:
                    try:
                        _stop(active)
                    except OSError:
                        pass
                core.close()
                return
            if os.name == "nt":
                # core.close() can invalidate core.process at any time.
                # Capture a local reference; a vanished PID is non-fatal.
                try:
                    active = core.process
                    pid = getattr(active, "pid", None)
                    if active is not None and isinstance(pid, int) and pid > 0 and active.poll() is None:
                        samples.append(windows_process_snapshot(pid))
                except (OSError, AttributeError, ValueError):
                    pass

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        core.start()
        if cancel.is_set():
            raise GenerationCancelled()
        body = json.dumps({
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens, "temperature": request.temperature,
            "stream": True, "cache_prompt": False,
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"http://{core.host}:{core.port}/v1/chat/completions",
            data=body, headers={"Content-Type": "application/json"}, method="POST")
        with core._urlopen(req, timeout=core.request_timeout_s) as response:
            for raw in response:
                if cancel.is_set():
                    raise GenerationCancelled()
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                msg = json.loads(data)
                choices = msg.get("choices") or []
                delta = choices[0].get("delta", {}) if choices else {}
                text = str(delta.get("content") or msg.get("content") or "")
                if text:
                    if first_at is None:
                        first_at = time.monotonic()
                    output.append(text)
                    on_chunk(text)
                if msg.get("timings"):
                    timings = msg["timings"]
        if cancel.is_set():
            raise GenerationCancelled()
        core.query_count += 1
        return {"return_code": 0, "stdout": "".join(output), "metrics": {
            "latency_ms": (time.monotonic() - started) * 1000,
            "ttft_ms": (first_at - started) * 1000 if first_at else None,
            "tokens_per_second": timings.get("predicted_per_second"),
            "working_set_bytes_max": _max_ram(samples, "working_set_bytes"),
            "private_bytes_max": _max_ram(samples, "private_bytes"),
            "physical_read_bytes": None,
        }}
    except Exception:
        # A child killed during model loading may raise RuntimeError ("exited")
        # rather than OSError. It is still a user cancellation.
        if cancel.is_set():
            raise GenerationCancelled() from None
        raise
    finally:
        done.set()
        watcher.join(timeout=3)


def generate_streamed(core: Any, request: GenerationRequest,
                      on_chunk: Callable[[str], None], cancel: threading.Event) -> dict:
    if cancel.is_set():
        raise GenerationCancelled()
    if isinstance(core, SubprocessPerQueryCore):
        return _subprocess_stream(core, request, on_chunk, cancel)
    if isinstance(core, PersistentCoreBackend):
        return _persistent_stream(core, request, on_chunk, cancel)
    # Support fake backends in unit tests. Production uses native backends above.
    measured = core.generate(request)
    if cancel.is_set():
        raise GenerationCancelled()
    if measured.get("stdout"):
        on_chunk(str(measured["stdout"]))
    return measured
