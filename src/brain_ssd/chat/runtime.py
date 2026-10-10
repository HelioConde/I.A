"""CPU-only Windows chat adapter, with optional SSD knowledge (noncanonical)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_ssd.local_runtime.backend import resolve_llama_executable
from brain_ssd.local_runtime.core_backend import (
    PersistentCoreBackend, SubprocessPerQueryCore, resolve_server_executable,
)
from brain_ssd.local_runtime.pipeline import (
    INDEX_RELATIVE, MANIFEST_RELATIVE, MODEL_RELATIVE, LocalBrainSSD,
)

PROFILES = {
    "economia": {"threads": 2, "context_size": 2048, "mode": "subprocess", "knowledge_budget": 1200},
    "equilibrado": {"threads": 4, "context_size": 4096, "mode": "subprocess", "knowledge_budget": 3500},
    "rapido": {"threads": 4, "context_size": 4096, "mode": "persistent", "knowledge_budget": 3500},
}


class LocalChatRuntime:
    """Real llama.cpp inference; greeting does not require an SSD corpus."""

    def __init__(self, root: Path, *, profile: str = "equilibrado", core_mode: str | None = None) -> None:
        if profile not in PROFILES:
            raise ValueError(f"Perfil desconhecido: {profile}")
        self.root = root.resolve()
        self.profile = profile
        settings = PROFILES[profile]
        self.core_mode = core_mode or settings["mode"]
        if self.core_mode not in ("subprocess", "persistent"):
            raise ValueError(f"Modo desconhecido: {self.core_mode}")
        self.knowledge_budget = int(settings["knowledge_budget"])
        self.model_path = self.root / MODEL_RELATIVE
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Modelo GGUF ausente: {self.model_path}. "
                "Coloque Qwen3-0.6B-Q8_0.gguf na pasta models/ e reinicie."
            )
        with self.model_path.open("rb") as stream:
            if stream.read(4) != b"GGUF":
                raise ValueError(f"Modelo inválido (assinatura GGUF ausente): {self.model_path}")
        self._completion_path: Path | None = None
        self._brain: LocalBrainSSD | None = None
        self._closed = False
        self.has_knowledge_files = (
            (self.root / MANIFEST_RELATIVE).is_file()
            and (self.root / INDEX_RELATIVE).is_file()
        )
        if self.core_mode == "persistent":
            executable = resolve_server_executable(self.root)
            self.core_backend = PersistentCoreBackend(
                executable, self.model_path,
                threads=int(settings["threads"]), context_size=int(settings["context_size"]),
            )
            try:
                self._completion_path = resolve_llama_executable(self.root)
            except FileNotFoundError:
                pass  # Optional SSD retrieval is unavailable without the frozen CLI.
        else:
            self._completion_path = resolve_llama_executable(self.root)
            self.core_backend = SubprocessPerQueryCore(
                self._completion_path, self.model_path,
                threads=int(settings["threads"]), context_size=int(settings["context_size"]),
            )

    def status(self) -> dict[str, Any]:
        available = self.has_knowledge_files and self._completion_path is not None
        return {
            "profile": self.profile,
            "core_mode": self.core_mode,
            "threads": PROFILES[self.profile]["threads"],
            "knowledge_available": available,
            "knowledge_note": (
                "Conhecimento SSD disponível"
                if available else "Base de conhecimento SSD opcional ausente; conversa ainda disponível"
            ),
        }

    def retrieve(self, query: str) -> dict[str, Any]:
        if not self.has_knowledge_files or self._completion_path is None:
            return {"status": "UNAVAILABLE", "sources": [], "activated_pages": [], "context": {"text": ""}}
        if self._brain is None:
            self._brain = LocalBrainSSD(self.root, executable=self._completion_path)
        return self._brain.retrieve(query)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                if self._brain is not None:
                    self._brain.close()
            finally:
                self.core_backend.close()
