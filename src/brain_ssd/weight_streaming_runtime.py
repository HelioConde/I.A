"""V2 preflight contracts; deliberately not an inference backend.

llama.cpp currently owns GGUF loading and every dense matmul needs its weights.
This module makes that constraint explicit before any future native loader work:
all tensors are mandatory unless an integration supplies a verified MoE expert
mapping.  It never routes experts, transfers weights, or generates tokens.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from brain_ssd.gguf_inspector import GGUFInspector, TensorInfo


@dataclass(frozen=True)
class TensorResidencyPlan:
    mandatory: tuple[TensorInfo, ...]
    declared_experts: tuple[TensorInfo, ...]
    total_bytes: int
    mandatory_bytes: int
    expert_bytes: int
    mode: str = "preflight_only"

    @property
    def is_dense_baseline(self) -> bool:
        return not self.declared_experts


def build_residency_plan(inspector: GGUFInspector, *,
                         expert_tensor_names: Iterable[str] = ()) -> TensorResidencyPlan:
    """Build an explicit, conservative tensor residency contract.

    ``expert_tensor_names`` is accepted only from a model-specific integration
    that has proved routing semantics.  Names are not inferred from strings;
    unknown names are rejected and shared tensors remain mandatory.
    """
    names = tuple(expert_tensor_names)
    if len(set(names)) != len(names):
        raise ValueError("Declared expert tensor names must be unique.")
    experts = tuple(inspector.tensor(name) for name in names)
    expert_set = set(names)
    mandatory = tuple(tensor for tensor in inspector.tensors if tensor.name not in expert_set)
    total = sum(tensor.size_bytes for tensor in inspector.tensors)
    expert_bytes = sum(tensor.size_bytes for tensor in experts)
    return TensorResidencyPlan(
        mandatory=mandatory, declared_experts=experts, total_bytes=total,
        mandatory_bytes=total - expert_bytes, expert_bytes=expert_bytes,
    )


def unsupported_inference_message() -> str:
    """Stable status for callers; never silently fall back or emulate logits."""
    return (
        "Weight streaming inference is not implemented. The conventional "
        "llama.cpp backend remains mandatory until a native loader contract "
        "proves complete dense-layer and MoE shared-tensor execution."
    )
