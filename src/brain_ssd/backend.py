from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    max_tokens: int = 48
    temperature: float = 0.0


class InferenceBackend(Protocol):
    @property
    def name(self) -> str: ...

    def command(self, request: GenerationRequest) -> Sequence[str]: ...


@dataclass(frozen=True)
class LlamaCppBackend:
    executable: Path
    model: Path
    threads: int = 1
    context_size: int = 512

    @property
    def name(self) -> str:
        return "llama.cpp-cpu"

    def command(self, request: GenerationRequest) -> Sequence[str]:
        if self.threads < 1:
            raise ValueError("threads must be >= 1")
        if not self.executable.is_file():
            raise FileNotFoundError(f"llama-cli not found: {self.executable}")
        if not self.model.is_file():
            raise FileNotFoundError(f"GGUF model not found: {self.model}")
        return (
            str(self.executable),
            "--model",
            str(self.model),
            "--prompt",
            request.prompt,
            "--n-predict",
            str(request.max_tokens),
            "--threads",
            str(self.threads),
            "--ctx-size",
            str(self.context_size),
            "--temp",
            str(request.temperature),
            "--device",
            "none",
            "--no-display-prompt",
            "--simple-io",
            "--no-warmup",
            "--reasoning",
            "off",
            "--perf",
        )
