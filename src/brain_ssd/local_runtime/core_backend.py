from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Protocol

from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.backend import LocalLlamaCppBackend
from brain_ssd.local_runtime.pipeline_support import run_measured
from brain_ssd.local_runtime.windows_metrics import ProcessSnapshot, windows_process_snapshot


SUBPROCESS_PER_QUERY = "SUBPROCESS_PER_QUERY"
PERSISTENT_CORE = "PERSISTENT_CORE"
CORE_MODES = {"subprocess": SUBPROCESS_PER_QUERY, "persistent": PERSISTENT_CORE}
CoreEventCallback = Callable[[str, dict[str, Any]], None]


class CoreBackend(Protocol):
    name: str
    mode: str
    runtime_path: Path

    def generate(
        self,
        request: GenerationRequest,
        *,
        on_first_output: Callable[[], None] | None = None,
        on_event: CoreEventCallback | None = None,
    ) -> dict[str, Any]: ...

    def close(self) -> None: ...


def generation_configuration(*, threads: int, context_size: int, max_tokens: int, temperature: float) -> dict[str, Any]:
    return {
        "temperature": temperature,
        "seed": None,
        "max_tokens": max_tokens,
        "sampling": "greedy_when_temperature_zero",
        "stop_sequences": [],
        "threads": threads,
        "context_size": context_size,
        "device": "none",
        "reasoning": "off",
    }


def resolve_server_executable(root: Path, explicit: Path | None = None) -> Path:
    candidates = tuple(
        path for path in (
            explicit,
            root / "third_party/llama.cpp/build-win-persistent/bin/llama-server.exe",
            root / "third_party/llama.cpp/build-win-persistent/bin/Release/llama-server.exe",
        ) if path is not None
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return Path(candidate).resolve()
    checked = "\n  - ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"experimental llama-server was not found. Checked:\n  - {checked}")


class SubprocessPerQueryCore:
    mode = SUBPROCESS_PER_QUERY

    def __init__(self, executable: Path, model: Path, *, threads: int = 4, context_size: int = 4096) -> None:
        self.backend = LocalLlamaCppBackend(executable, model, threads=threads, context_size=context_size)
        self.name = "llama.cpp-subprocess-per-query"
        self.runtime_path = executable.resolve()
        self.model_loads = 0
        self.query_count = 0

    def generate(
        self,
        request: GenerationRequest,
        *,
        on_first_output: Callable[[], None] | None = None,
        on_event: CoreEventCallback | None = None,
    ) -> dict[str, Any]:
        if on_event:
            on_event("CORE_PROCESS_STARTING", {"core_mode": self.mode})
            on_event("CORE_MODEL_LOADING", {"model_loads": self.model_loads + 1})
            on_event("CORE_REQUEST_STARTED", {"query_number": self.query_count + 1})
        measured = run_measured(self.backend.command(request), on_first_output=on_first_output)
        self.model_loads += 1
        self.query_count += 1
        metrics = dict(measured.get("metrics", {}))
        metrics.update({
            "core_mode": self.mode,
            "model_loads": self.model_loads,
            "queries_served": self.query_count,
            "reloads_avoided": 0,
            "core_reuse_ratio": 1.0,
            "reload_avoidance_rate": 0.0,
            "one_time_startup_cost_ms": 0.0,
        })
        measured["metrics"] = metrics
        if on_event:
            on_event("CORE_REQUEST_COMPLETED", metrics)
        return measured

    def close(self) -> None:
        return None


def _available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _cpu_seconds(snapshot: ProcessSnapshot) -> float | None:
    values = (snapshot.cpu_user_seconds, snapshot.cpu_kernel_seconds)
    if all(value is None for value in values):
        return None
    return sum(value or 0.0 for value in values)


def _metric_values(samples: list[ProcessSnapshot], name: str) -> list[int | float]:
    return [value for sample in samples if (value := getattr(sample, name)) is not None]


def _sample_delta(samples: list[ProcessSnapshot], name: str) -> int | float | None:
    values = _metric_values(samples, name)
    return max(0, values[-1] - values[0]) if len(values) >= 2 else None


class PersistentCoreBackend:
    mode = PERSISTENT_CORE

    def __init__(
        self,
        executable: Path,
        model: Path,
        *,
        threads: int = 4,
        context_size: int = 4096,
        host: str = "127.0.0.1",
        port: int | None = None,
        ready_timeout_s: float = 90.0,
        request_timeout_s: float = 300.0,
        process_factory: Callable[..., Any] | None = None,
        urlopen: Callable[..., Any] | None = None,
    ) -> None:
        if host != "127.0.0.1":
            raise ValueError("persistent Core must bind only to 127.0.0.1")
        self.runtime_path = executable.resolve()
        self.model = model.resolve()
        self.threads = threads
        self.context_size = context_size
        self.host = host
        self.port = port
        self.ready_timeout_s = ready_timeout_s
        self.request_timeout_s = request_timeout_s
        self.name = "llama.cpp-persistent-server"
        self.model_loads = 0
        self.query_count = 0
        self.process: Any | None = None
        self.ready = False
        self.startup_metrics: dict[str, Any] = {}
        self._process_factory = process_factory or subprocess.Popen
        self._urlopen = urlopen or urllib.request.urlopen
        self._log_tail: deque[str] = deque(maxlen=4000)
        self._log_threads: list[threading.Thread] = []
        self._first_log_at: float | None = None
        self._last_event_callback: CoreEventCallback | None = None
        self._lock = threading.RLock()

    @property
    def reloads_avoided(self) -> int:
        return max(0, self.query_count - self.model_loads)

    @property
    def core_reuse_ratio(self) -> float:
        return self.query_count / self.model_loads if self.model_loads else 0.0

    @property
    def reload_avoidance_rate(self) -> float:
        possible = max(0, self.query_count - 1)
        return self.reloads_avoided / possible if possible else 0.0

    def command(self) -> tuple[str, ...]:
        if self.threads < 1:
            raise ValueError("threads must be >= 1")
        if not self.runtime_path.is_file():
            raise FileNotFoundError(f"llama-server not found: {self.runtime_path}")
        if not self.model.is_file():
            raise FileNotFoundError(f"GGUF model not found: {self.model}")
        if self.port is None:
            self.port = _available_loopback_port()
        return (
            str(self.runtime_path), "--model", str(self.model),
            "--threads", str(self.threads), "--threads-batch", str(self.threads),
            "--ctx-size", str(self.context_size), "--device", "none", "--no-warmup",
            "--host", self.host, "--port", str(self.port), "--no-webui", "--metrics",
            "--reasoning", "off", "--parallel", "1", "--cache-ram", "0", "--no-cache-idle-slots",
        )

    def _read_log(self, stream: Any) -> None:
        while True:
            line = stream.readline()
            if not line:
                break
            if self._first_log_at is None:
                self._first_log_at = time.monotonic()
            self._log_tail.append(str(line).rstrip())

    def _launch_process(self) -> Any:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        process = self._process_factory(
            list(self.command()), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=creation_flags, env=os.environ.copy(),
        )
        self._log_threads = [
            threading.Thread(target=self._read_log, args=(process.stdout,), daemon=True),
            threading.Thread(target=self._read_log, args=(process.stderr,), daemon=True),
        ]
        for thread in self._log_threads:
            thread.start()
        return process

    def _health(self) -> dict[str, Any] | None:
        request = urllib.request.Request(f"http://{self.host}:{self.port}/health", method="GET")
        try:
            with self._urlopen(request, timeout=1.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return None

    def start(self, on_event: CoreEventCallback | None = None) -> dict[str, Any]:
        with self._lock:
            if self.ready and self.process is not None and self.process.poll() is None:
                return dict(self.startup_metrics)
            self._last_event_callback = on_event or self._last_event_callback
            callback = on_event or (lambda *_: None)
            callback("CORE_PROCESS_STARTING", {"core_mode": self.mode})
            started = time.monotonic()
            self._first_log_at = None
            self.process = self._launch_process()
            callback("CORE_MODEL_LOADING", {"pid": self.process.pid, "port": self.port})
            deadline = started + self.ready_timeout_s
            try:
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        tail = "\n".join(self._log_tail)[-4000:]
                        raise RuntimeError(f"persistent Core exited with code {self.process.returncode}: {tail}")
                    health = self._health()
                    if health and health.get("status") == "ok":
                        ready_at = time.monotonic()
                        snapshot = windows_process_snapshot(self.process.pid)
                        process_startup_ms = ((self._first_log_at or ready_at) - started) * 1000
                        ready_ms = (ready_at - started) * 1000
                        self.ready = True
                        self.model_loads += 1
                        self.startup_metrics = {
                            "process_startup_ms": process_startup_ms,
                            "model_load_ms": max(0.0, ready_ms - process_startup_ms),
                            "model_load_measurement": "ready_time_minus_first_process_log; includes server initialization after first log",
                            "persistent_core_ready_ms": ready_ms,
                            "working_set_bytes_after_load": snapshot.working_set_bytes,
                            "private_bytes_after_load": snapshot.private_bytes,
                            "threads_after_load": snapshot.thread_count,
                            "handles_after_load": snapshot.handle_count,
                            "cpu_time_seconds_after_load": _cpu_seconds(snapshot),
                            "pid": self.process.pid,
                            "host": self.host,
                            "port": self.port,
                            "model_loads": self.model_loads,
                        }
                        callback("CORE_READY", dict(self.startup_metrics))
                        return dict(self.startup_metrics)
                    time.sleep(0.1)
                raise TimeoutError(f"persistent Core readiness timed out after {self.ready_timeout_s:.1f}s")
            except BaseException:
                self.close()
                raise

    def _stream_completion(
        self,
        request: GenerationRequest,
        on_first_output: Callable[[], None] | None,
    ) -> tuple[str, dict[str, Any], float | None, dict[str, Any]]:
        payload = {
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
            "cache_prompt": False,
        }
        http_request = urllib.request.Request(
            f"http://{self.host}:{self.port}/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        started = time.monotonic()
        first_token_at: float | None = None
        content: list[str] = []
        final: dict[str, Any] = {}
        with self._urlopen(http_request, timeout=self.request_timeout_s) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    continue
                event = json.loads(data)
                choices = event.get("choices") or []
                delta = choices[0].get("delta", {}) if choices else {}
                chunk = str(delta.get("content") or event.get("content") or "")
                if chunk:
                    if first_token_at is None:
                        first_token_at = time.monotonic()
                        if on_first_output:
                            on_first_output()
                    content.append(chunk)
                if event.get("stop") or event.get("timings") or (choices and choices[0].get("finish_reason")):
                    final = event
        ttft_ms = (first_token_at - started) * 1000 if first_token_at is not None else None
        return "".join(content), dict(final.get("timings") or {}), ttft_ms, final

    def generate(
        self,
        request: GenerationRequest,
        *,
        on_first_output: Callable[[], None] | None = None,
        on_event: CoreEventCallback | None = None,
    ) -> dict[str, Any]:
        callback = on_event or (lambda *_: None)
        self._last_event_callback = on_event or self._last_event_callback
        reused = self.ready
        self.start(on_event=on_event)
        if reused:
            callback("CORE_REUSED", {"queries_served": self.query_count, "model_loads": self.model_loads})
        callback("CORE_REQUEST_STARTED", {"query_number": self.query_count + 1, "port": self.port})
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("persistent Core is not running")
        samples: list[ProcessSnapshot] = []
        sample_stop = threading.Event()

        def sample() -> None:
            while not sample_stop.is_set():
                samples.append(windows_process_snapshot(self.process.pid))
                sample_stop.wait(0.025)

        sampler = threading.Thread(target=sample, daemon=True)
        started = time.monotonic()
        sampler.start()
        try:
            stdout, timings, ttft_ms, final = self._stream_completion(request, on_first_output)
        finally:
            sample_stop.set()
            sampler.join(timeout=2)
            if self.process is not None:
                samples.append(windows_process_snapshot(self.process.pid))
        latency_s = max(0.000001, time.monotonic() - started)
        self.query_count += 1
        cpu_values = [_cpu_seconds(snapshot) for snapshot in samples]
        cpu_values = [value for value in cpu_values if value is not None]
        cpu_delta = max(0.0, cpu_values[-1] - cpu_values[0]) if len(cpu_values) >= 2 else None
        user_values = _metric_values(samples, "cpu_user_seconds")
        kernel_values = _metric_values(samples, "cpu_kernel_seconds")
        user_delta = max(0.0, user_values[-1] - user_values[0]) if len(user_values) >= 2 else None
        kernel_delta = max(0.0, kernel_values[-1] - kernel_values[0]) if len(kernel_values) >= 2 else None
        cpu_samples: list[float] = []
        for previous, current in zip(samples, samples[1:]):
            elapsed = current.timestamp - previous.timestamp
            previous_cpu = _cpu_seconds(previous)
            current_cpu = _cpu_seconds(current)
            if elapsed > 0 and previous_cpu is not None and current_cpu is not None:
                cpu_samples.append(100.0 * max(0.0, current_cpu - previous_cpu) / elapsed)
        working = _metric_values(samples, "working_set_bytes")
        private = _metric_values(samples, "private_bytes")
        handles = _metric_values(samples, "handle_count")
        threads = _metric_values(samples, "thread_count")
        available = _metric_values(samples, "system_available_ram_bytes")
        metrics = {
            "latency_ms": latency_s * 1000,
            "ttft_ms": ttft_ms,
            "working_set_bytes_min": min(working) if working else None,
            "working_set_bytes_max": max(working) if working else None,
            "private_bytes_min": min(private) if private else None,
            "private_bytes_max": max(private) if private else None,
            "cpu_user_seconds": user_delta,
            "cpu_kernel_seconds": kernel_delta,
            "cpu_time_seconds": cpu_delta,
            "cpu_percent_total_average": 100.0 * cpu_delta / latency_s if cpu_delta is not None else None,
            "cpu_percent_total_peak": max(cpu_samples) if cpu_samples else None,
            "read_operations_delta": _sample_delta(samples, "read_operations"),
            "write_operations_delta": _sample_delta(samples, "write_operations"),
            "read_transfer_bytes_delta": _sample_delta(samples, "read_transfer_bytes"),
            "write_transfer_bytes_delta": _sample_delta(samples, "write_transfer_bytes"),
            "handle_count_min": min(handles) if handles else None,
            "handle_count_max": max(handles) if handles else None,
            "thread_count_min": min(threads) if threads else None,
            "thread_count_max": max(threads) if threads else None,
            "system_available_ram_bytes_min": min(available) if available else None,
            "tokens_per_second": timings.get("predicted_per_second"),
            "prompt_tokens_per_second": timings.get("prompt_per_second"),
            "generated_tokens": timings.get("predicted_n") or final.get("tokens_predicted"),
            "prompt_tokens": timings.get("prompt_n") or final.get("tokens_evaluated"),
            "model_load_ms": 0.0,
            "prompt_eval_ms": timings.get("prompt_ms"),
            "generation_eval_ms": timings.get("predicted_ms"),
            "backend_total_ms": latency_s * 1000,
            "core_mode": self.mode,
            "model_loads": self.model_loads,
            "queries_served": self.query_count,
            "reloads_avoided": self.reloads_avoided,
            "core_reuse_ratio": self.core_reuse_ratio,
            "reload_avoidance_rate": self.reload_avoidance_rate,
            "one_time_startup_cost_ms": self.startup_metrics.get("persistent_core_ready_ms"),
            "persistent_reserved_memory": self.startup_metrics.get("working_set_bytes_after_load"),
        }
        callback("CORE_REQUEST_COMPLETED", dict(metrics))
        return {
            "command": ["HTTP", f"http://{self.host}:{self.port}/v1/chat/completions"],
            "return_code": 0,
            "stdout": stdout,
            "stderr": "",
            "metrics": metrics,
            "samples": [asdict(snapshot) for snapshot in samples],
            "measurement_semantics": {
                "ttft_ms": "Elapsed from HTTP request start to first non-empty streamed token.",
                "working_set_bytes_max": "Maximum sampled resident working set of the persistent llama-server process during this request.",
                "private_bytes_max": "Maximum sampled private commit of the persistent llama-server process during this request.",
                "model_load_ms": "Zero per request; one-time startup is reported separately.",
                "physical_read_bytes": "NOT_MEASURED on Windows.",
            },
            "runtime_report": {
                "configured_threads": self.threads,
                "server": True,
                "host": self.host,
                "port": self.port,
                "startup": dict(self.startup_metrics),
            },
        }

    def close(self) -> None:
        with self._lock:
            process = self.process
            callback = self._last_event_callback or (lambda *_: None)
            if process is not None and process.poll() is None:
                callback("CORE_SHUTDOWN", {"pid": process.pid, "queries_served": self.query_count})
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for thread in self._log_threads:
                thread.join(timeout=1)
            self.ready = False
            self.process = None

    def status(self) -> dict[str, Any]:
        running = bool(self.process is not None and self.process.poll() is None)
        return {
            "mode": self.mode,
            "ready": self.ready and running,
            "running": running,
            "pid": self.process.pid if running else None,
            "host": self.host,
            "port": self.port,
            "model_loads": self.model_loads,
            "queries_served": self.query_count,
            "reloads_avoided": self.reloads_avoided,
            "core_reuse_ratio": self.core_reuse_ratio,
            "reload_avoidance_rate": self.reload_avoidance_rate,
            "startup": dict(self.startup_metrics),
            "log_tail": list(self._log_tail)[-40:],
        }
