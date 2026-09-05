from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from brain_ssd.backend import GenerationRequest, LlamaCppBackend


FROZEN_LLAMA_COMMIT = "217df17ac30ba2a8c374088772f81926cc5beee3"


def executable_candidates(root: Path, explicit: Path | None = None, *, windows: bool | None = None) -> tuple[Path, ...]:
    use_windows = os.name == "nt" if windows is None else windows
    suffix = ".exe" if use_windows else ""
    values = [
        explicit,
        root / f"third_party/llama.cpp/build-win/bin/llama-completion{suffix}",
        root / f"third_party/llama.cpp/build-win/bin/Release/llama-completion{suffix}",
        root / f"build/llama.cpp/bin/llama-completion{suffix}",
        root / f"third_party/llama.cpp/build/bin/llama-completion{suffix}",
    ]
    unique: list[Path] = []
    for value in values:
        if value is not None and value not in unique:
            unique.append(Path(value))
    return tuple(unique)


def resolve_llama_executable(root: Path, explicit: Path | None = None, *, windows: bool | None = None) -> Path:
    candidates = executable_candidates(root, explicit, windows=windows)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    checked = "\n  - ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"llama-completion was not found. Checked:\n  - {checked}")


def probe_llama(executable: Path, timeout_s: float = 15.0) -> dict[str, object]:
    version = subprocess.run(
        [str(executable), "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s,
    )
    combined = (version.stdout + "\n" + version.stderr).strip()
    devices = subprocess.run(
        [str(executable), "--list-devices"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s,
    )
    device_output = (devices.stdout + "\n" + devices.stderr).strip()
    return {
        "path": str(executable),
        "version_return_code": version.returncode,
        "version_output": combined,
        # llama.cpp's version banner abbreviates this checkout to nine characters.
        "frozen_commit_match": FROZEN_LLAMA_COMMIT[:9] in combined,
        "devices_return_code": devices.returncode,
        "devices_output": device_output,
        "cpu_only_build": "(none)" in device_output.casefold(),
    }


@dataclass(frozen=True, slots=True)
class LocalLlamaCppBackend:
    executable: Path
    model: Path
    threads: int = 4
    context_size: int = 4096

    @property
    def name(self) -> str:
        return "llama.cpp-cpu-local"

    def command(self, request: GenerationRequest) -> Sequence[str]:
        frozen = LlamaCppBackend(
            executable=self.executable,
            model=self.model,
            threads=self.threads,
            context_size=self.context_size,
        )
        command = list(frozen.command(request))
        command.extend(("--conversation", "--single-turn"))
        return tuple(command)
