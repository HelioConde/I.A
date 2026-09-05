from __future__ import annotations

import ctypes
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable, Sequence


@dataclass(slots=True)
class ProcessSnapshot:
    timestamp: float
    working_set_bytes: int | None = None
    peak_working_set_bytes: int | None = None
    private_bytes: int | None = None
    page_fault_count: int | None = None
    cpu_user_seconds: float | None = None
    cpu_kernel_seconds: float | None = None
    read_operations: int | None = None
    write_operations: int | None = None
    read_transfer_bytes: int | None = None
    write_transfer_bytes: int | None = None
    handle_count: int | None = None
    thread_count: int | None = None
    system_total_ram_bytes: int | None = None
    system_available_ram_bytes: int | None = None


if os.name == "nt":
    from ctypes import wintypes

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]


def _filetime_seconds(value: object) -> float:
    raw = (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)
    return raw / 10_000_000.0


def _system_memory() -> tuple[int | None, int | None]:
    if os.name != "nt":
        return None, None
    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None, None
    return int(status.ullTotalPhys), int(status.ullAvailPhys)


def windows_process_snapshot(pid: int) -> ProcessSnapshot:
    if os.name != "nt":
        return ProcessSnapshot(timestamp=time.monotonic())
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD)
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    kernel32.GetProcessIoCounters.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    kernel32.GetProcessIoCounters.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.GetProcessHandleCount.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    kernel32.GetProcessHandleCount.restype = wintypes.BOOL
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_VM_READ = 0x0010
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return ProcessSnapshot(timestamp=time.monotonic())
    try:
        memory = PROCESS_MEMORY_COUNTERS_EX()
        memory.cb = ctypes.sizeof(memory)
        memory_ok = bool(psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb))

        io = IO_COUNTERS()
        io_ok = bool(kernel32.GetProcessIoCounters(handle, ctypes.byref(io)))

        creation, exit_time, kernel, user = (wintypes.FILETIME() for _ in range(4))
        cpu_ok = bool(kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)))

        handles = wintypes.DWORD()
        handle_ok = bool(kernel32.GetProcessHandleCount(handle, ctypes.byref(handles)))
        total_ram, available_ram = _system_memory()

        thread_count = None
        try:
            import psutil  # optional; the runtime never requires it
            thread_count = int(psutil.Process(pid).num_threads())
        except Exception:
            # Optional enrichment must never fail the measured child when its PID
            # exits between the native snapshot and this thread-count query.
            pass

        return ProcessSnapshot(
            timestamp=time.monotonic(),
            working_set_bytes=int(memory.WorkingSetSize) if memory_ok else None,
            peak_working_set_bytes=int(memory.PeakWorkingSetSize) if memory_ok else None,
            private_bytes=int(memory.PrivateUsage) if memory_ok else None,
            page_fault_count=int(memory.PageFaultCount) if memory_ok else None,
            cpu_user_seconds=_filetime_seconds(user) if cpu_ok else None,
            cpu_kernel_seconds=_filetime_seconds(kernel) if cpu_ok else None,
            read_operations=int(io.ReadOperationCount) if io_ok else None,
            write_operations=int(io.WriteOperationCount) if io_ok else None,
            read_transfer_bytes=int(io.ReadTransferCount) if io_ok else None,
            write_transfer_bytes=int(io.WriteTransferCount) if io_ok else None,
            handle_count=int(handles.value) if handle_ok else None,
            thread_count=thread_count,
            system_total_ram_bytes=total_ram,
            system_available_ram_bytes=available_ram,
        )
    finally:
        kernel32.CloseHandle(handle)


def _reader(stream: object, name: str, output: list[str], events: queue.Queue[tuple[str, float]]) -> None:
    while True:
        chunk = stream.read(1)
        if not chunk:
            break
        output.append(chunk)
        events.put((name, time.monotonic()))


def _sample_delta(samples: list[ProcessSnapshot], key: str) -> int | float | None:
    values = [getattr(sample, key) for sample in samples if getattr(sample, key) is not None]
    return max(0, values[-1] - values[0]) if len(values) >= 2 else None


def _max(samples: list[ProcessSnapshot], key: str) -> int | float | None:
    values = [getattr(sample, key) for sample in samples if getattr(sample, key) is not None]
    return max(values) if values else None


def _min(samples: list[ProcessSnapshot], key: str) -> int | float | None:
    values = [getattr(sample, key) for sample in samples if getattr(sample, key) is not None]
    return min(values) if values else None


def _perf_number(stderr: str, label: str) -> float | None:
    prefix = r"^(?:.*?common_perf_print:\s*)?"
    pattern = rf"{prefix}{re.escape(label)}\s*=.*?([0-9]+(?:\.[0-9]+)?)\s+tokens per second"
    match = re.search(pattern, stderr, flags=re.IGNORECASE | re.MULTILINE)
    return float(match.group(1)) if match else None


def _perf_tokens(stderr: str, label: str) -> int | None:
    prefix = r"^(?:.*?common_perf_print:\s*)?"
    pattern = rf"{prefix}{re.escape(label)}\s*=.*?/\s*([0-9]+)\s+(?:tokens?|runs)"
    match = re.search(pattern, stderr, flags=re.IGNORECASE | re.MULTILINE)
    return int(match.group(1)) if match else None


def _perf_ms(stderr: str, label: str) -> float | None:
    prefix = r"^(?:.*?common_perf_print:\s*)?"
    pattern = rf"{prefix}{re.escape(label)}\s*=\s*([0-9]+(?:\.[0-9]+)?)\s+ms"
    match = re.search(pattern, stderr, flags=re.IGNORECASE | re.MULTILINE)
    return float(match.group(1)) if match else None


def _runtime_report(stderr: str) -> dict[str, object]:
    thread_match = re.search(r"llama threadpool init, n_threads\s*=\s*([0-9]+)", stderr, re.IGNORECASE)
    system_match = re.search(r"system_info:\s*(.+)", stderr, re.IGNORECASE)
    system_info = system_match.group(1).strip() if system_match else None
    features: dict[str, bool | None] = {}
    for feature in ("AVX", "AVX2", "AVX512", "FMA", "F16C", "OPENMP", "BLAS"):
        match = re.search(rf"\b{feature}\s*=\s*([01])\b", system_info or "", re.IGNORECASE)
        features[feature.casefold()] = bool(int(match.group(1))) if match else None
    return {
        "configured_threads": int(thread_match.group(1)) if thread_match else None,
        "system_info": system_info,
        "features": features,
        "cpu_backend": "llama.cpp CPU (--device none)",
    }


def run_measured_windows(
    command: Sequence[str],
    *,
    sample_interval_s: float = 0.025,
    on_first_output: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Run a child with argument-safe invocation and sample documented Windows counters."""
    started = time.monotonic()
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    child_environment = os.environ.copy()
    child_environment.setdefault("PYTHONUTF8", "1")
    child_environment.setdefault("PYTHONIOENCODING", "utf-8")
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=0,
        creationflags=creation_flags,
        env=child_environment,
    )
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    events: queue.Queue[tuple[str, float]] = queue.Queue()
    stdout_thread = threading.Thread(target=_reader, args=(process.stdout, "stdout", stdout_parts, events), daemon=True)
    stderr_thread = threading.Thread(target=_reader, args=(process.stderr, "stderr", stderr_parts, events), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    samples: list[ProcessSnapshot] = []
    first_output_at: float | None = None
    callback_sent = False
    try:
        while process.poll() is None:
            snapshot = windows_process_snapshot(process.pid)
            samples.append(snapshot)
            while True:
                try:
                    stream_name, event_at = events.get_nowait()
                except queue.Empty:
                    break
                if stream_name == "stdout" and first_output_at is None:
                    first_output_at = event_at
                    if on_first_output and not callback_sent:
                        callback_sent = True
                        on_first_output()
            time.sleep(sample_interval_s)
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        raise
    finally:
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
    finished = time.monotonic()
    if first_output_at is None and stdout_parts:
        first_output_at = finished
        if on_first_output and not callback_sent:
            on_first_output()
    if not samples:
        samples.append(windows_process_snapshot(process.pid))

    stderr = "".join(stderr_parts)
    cpu_seconds = sum(value or 0 for value in (_sample_delta(samples, "cpu_user_seconds"), _sample_delta(samples, "cpu_kernel_seconds")))
    latency_s = max(0.000001, finished - started)
    logical_cpus = max(1, os.cpu_count() or 1)
    cpu_samples: list[float] = []
    for previous, current in zip(samples, samples[1:]):
        elapsed = current.timestamp - previous.timestamp
        if elapsed <= 0:
            continue
        if None in (previous.cpu_user_seconds, previous.cpu_kernel_seconds, current.cpu_user_seconds, current.cpu_kernel_seconds):
            continue
        previous_cpu = previous.cpu_user_seconds + previous.cpu_kernel_seconds
        current_cpu = current.cpu_user_seconds + current.cpu_kernel_seconds
        cpu_samples.append(100.0 * max(0.0, current_cpu - previous_cpu) / elapsed)
    metrics = {
        "latency_ms": latency_s * 1000,
        "ttft_ms": (first_output_at - started) * 1000 if first_output_at is not None else None,
        "working_set_bytes_max": _max(samples, "working_set_bytes"),
        "peak_working_set_bytes_max": _max(samples, "peak_working_set_bytes"),
        "private_bytes_max": _max(samples, "private_bytes"),
        "page_fault_count_delta": _sample_delta(samples, "page_fault_count"),
        "cpu_user_seconds": _sample_delta(samples, "cpu_user_seconds"),
        "cpu_kernel_seconds": _sample_delta(samples, "cpu_kernel_seconds"),
        "cpu_percent_total_average": 100.0 * cpu_seconds / latency_s,
        "cpu_percent_normalized_average": 100.0 * cpu_seconds / latency_s / logical_cpus,
        "cpu_percent_total_peak": max(cpu_samples) if cpu_samples else None,
        "cpu_percent_normalized_peak": max(cpu_samples) / logical_cpus if cpu_samples else None,
        "read_operations_delta": _sample_delta(samples, "read_operations"),
        "write_operations_delta": _sample_delta(samples, "write_operations"),
        "read_transfer_bytes_delta": _sample_delta(samples, "read_transfer_bytes"),
        "write_transfer_bytes_delta": _sample_delta(samples, "write_transfer_bytes"),
        "handle_count_max": _max(samples, "handle_count"),
        "thread_count_max": _max(samples, "thread_count"),
        "system_total_ram_bytes": _max(samples, "system_total_ram_bytes"),
        "system_available_ram_bytes_min": _min(samples, "system_available_ram_bytes"),
        "tokens_per_second": _perf_number(stderr, "eval time"),
        "prompt_tokens_per_second": _perf_number(stderr, "prompt eval time"),
        "generated_tokens": _perf_tokens(stderr, "eval time"),
        "prompt_tokens": _perf_tokens(stderr, "prompt eval time"),
        "model_load_ms": _perf_ms(stderr, "load time"),
        "prompt_eval_ms": _perf_ms(stderr, "prompt eval time"),
        "generation_eval_ms": _perf_ms(stderr, "eval time"),
        "backend_total_ms": _perf_ms(stderr, "total time"),
        "physical_read_bytes": None,
        "pss_bytes_max": None,
        "anonymous_bytes_max": None,
        "rss_file_bytes_max": None,
        "temperature_c": None,
    }
    return {
        "command": list(command),
        "return_code": process.returncode,
        "stdout": "".join(stdout_parts),
        "stderr": stderr,
        "metrics": metrics,
        "measurement_semantics": {
            "read_transfer_bytes_delta": "Process I/O transfer counter; not a physical SSD-read measurement.",
            "working_set_bytes_max": "Maximum sampled resident working set for the llama.cpp child.",
            "private_bytes_max": "Maximum sampled private commit for the llama.cpp child.",
            "physical_read_bytes": "NOT_MEASURED on Windows native functional runtime.",
            "pss_bytes_max": "UNSUPPORTED on Windows; Linux /proc semantics were not emulated.",
        },
        "samples": [asdict(sample) for sample in samples],
        "runtime_report": _runtime_report(stderr),
    }
