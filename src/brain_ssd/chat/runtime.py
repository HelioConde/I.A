"""CPU-only Windows chat adapter, with optional SSD knowledge (noncanonical)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_ssd.local_runtime.backend import resolve_llama_executable
from brain_ssd.chat.startup_diagnostics import ChatStartupError
from brain_ssd.local_runtime.core_backend import (
    PersistentCoreBackend, SubprocessPerQueryCore, resolve_server_executable,
)
from brain_ssd.local_runtime.pipeline import (
    INDEX_RELATIVE, MANIFEST_RELATIVE, MODEL_RELATIVE, LocalBrainSSD,
)

MIN_PLAUSIBLE_GGUF_BYTES = 64 * 1024 * 1024
COMMUNITY_RUNTIME = Path("third_party/llama.cpp/runtime-win-cpu-x64/bin")


def resolve_chat_completion(root: Path) -> Path:
    """Interactive chat supports a verified official release as fallback.

    The frozen research backend still resolves its own pinned checkout;
    the community release is isolated from those canonical measurements.
    """
    candidate = Path(root) / COMMUNITY_RUNTIME / "llama-completion.exe"
    if candidate.is_file():
        return candidate.resolve()
    return resolve_llama_executable(root)


def resolve_chat_server(root: Path) -> Path:
    candidate = Path(root) / COMMUNITY_RUNTIME / "llama-server.exe"
    if candidate.is_file():
        return candidate.resolve()
    return resolve_server_executable(root)

PROFILES = {
    "economia": {"threads": 2, "context_size": 2048, "mode": "subprocess", "knowledge_budget": 1200, "prompt_budget_bytes": 3600},
    "equilibrado": {"threads": 4, "context_size": 4096, "mode": "subprocess", "knowledge_budget": 3500, "prompt_budget_bytes": 7600},
    "rapido": {"threads": 4, "context_size": 4096, "mode": "persistent", "knowledge_budget": 3500, "prompt_budget_bytes": 7600},
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
        self.prompt_budget_bytes = int(settings["prompt_budget_bytes"])
        self.model_path = self.root / MODEL_RELATIVE
        if not self.model_path.is_file():
            raise ChatStartupError("MODEL_MISSING")
        try:
            # Avoid invoking a native process on a truncated download.
            if self.model_path.stat().st_size < MIN_PLAUSIBLE_GGUF_BYTES:
                raise ChatStartupError("MODEL_INVALID")
            with self.model_path.open("rb") as stream:
                if stream.read(4) != b"GGUF":
                    raise ChatStartupError("MODEL_INVALID")
        except OSError as exc:
            raise ChatStartupError("MODEL_UNREADABLE") from exc
        self._completion_path: Path | None = None
        self._brain: LocalBrainSSD | None = None
        self._closed = False
        self.has_knowledge_files = (
            (self.root / MANIFEST_RELATIVE).is_file()
            and (self.root / INDEX_RELATIVE).is_file()
            and (self.root / MANIFEST_RELATIVE).with_name("brain.dat").is_file()
        )
        if self.core_mode == "persistent":
            try:
                executable = resolve_chat_server(self.root)
            except FileNotFoundError as exc:
                raise ChatStartupError("SERVER_MISSING") from exc
            self.core_backend = PersistentCoreBackend(
                executable, self.model_path,
                threads=int(settings["threads"]), context_size=int(settings["context_size"]),
            )
            try:
                self._completion_path = resolve_llama_executable(self.root)
            except FileNotFoundError:
                try:
                    # Chat retrieval is noncanonical: use the official CPU binary
                    # when the historically frozen research binary is absent.
                    self._completion_path = resolve_chat_completion(self.root)
                except FileNotFoundError:
                    pass  # No CLI available for optional retrieval.
        else:
            try:
                executable = resolve_chat_completion(self.root)
            except FileNotFoundError as exc:
                raise ChatStartupError("CORE_MISSING") from exc
            try:
                # Prefer the frozen research executable when installed; keep
                # the official binary as a chat-only retrieval fallback.
                self._completion_path = resolve_llama_executable(self.root)
            except FileNotFoundError:
                self._completion_path = executable
            self.core_backend = SubprocessPerQueryCore(
                executable, self.model_path,
                threads=int(settings["threads"]), context_size=int(settings["context_size"]),
            )

    def status(self) -> dict[str, Any]:
        available = self.has_knowledge_files and self._completion_path is not None
        return {
            "profile": self.profile,
            "core_mode": self.core_mode,
            "interactive_runtime": ("official_cpu_distribution"
                if self.core_backend.runtime_path.parent == (self.root / COMMUNITY_RUNTIME).resolve()
                else "frozen_checkout"),
            "threads": PROFILES[self.profile]["threads"],
            "prompt_budget_bytes": self.prompt_budget_bytes,
            "knowledge_cache": "per_query" if self.profile == "economia" else "session",
            "knowledge_available": available,
            "retrieval_runtime": (
                "official_cpu_distribution"
                if self._completion_path is not None
                and self._completion_path.parent == (self.root / COMMUNITY_RUNTIME).resolve()
                else "frozen_checkout" if self._completion_path is not None else "unavailable"
            ),
            "knowledge_note": (
                "Arquivos SSD e executável de recuperação encontrados; ainda é necessário validar uma consulta real"
                if available else "Recuperação SSD indisponível; o chat simples continua disponível"
            ),
        }

    def retrieve(self, query: str) -> dict[str, Any]:
        if not self.has_knowledge_files or self._completion_path is None:
            return {"status": "UNAVAILABLE", "sources": [], "activated_pages": [], "context": {"text": ""}}
        if self.profile == "economia":
            # Don't retain a large manifest/index across idle chat turns.
            # Trade SSD reload + CPU for reduced idle memory; opt-in by profile.
            with LocalBrainSSD(self.root, executable=self._completion_path) as short_lived:
                return short_lived.retrieve(query)
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
