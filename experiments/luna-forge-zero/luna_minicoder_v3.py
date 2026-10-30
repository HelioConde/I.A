"""Independent character-level completion model for Luna MiniCoder V3."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import torch
from torch import nn
from torch.nn import functional as F

from luna_codegen_model import CausalBlock


PAD_ID = 128
EOS_ID = 129
VOCAB_SIZE = 130


@dataclass
class V3Config:
    vocab: int = VOCAB_SIZE
    block: int = 512
    width: int = 32
    heads: int = 4
    layers: int = 1


def encode_prompt(text: str) -> list[int]:
    if not isinstance(text, str) or not text:
        raise ValueError("prompt must be a non-empty string")
    try:
        return list(text.encode("ascii"))
    except UnicodeEncodeError as error:
        raise ValueError("V3 prompts must be ASCII") from error


def encode_completion(text: str) -> list[int]:
    if not isinstance(text, str) or not text:
        raise ValueError("completion must be a non-empty string")
    try:
        return list(text.encode("ascii")) + [EOS_ID]
    except UnicodeEncodeError as error:
        raise ValueError("V3 completions must be ASCII") from error


def make_prompt(task: dict) -> str:
    return (
        f"TASK: {task['objective']}\n"
        "LANGUAGE: JavaScript\n"
        f"FUNCTION: {task['function_name']}({task['parameters']})\n"
        "CODE:\n"
    )


def collate_completions(examples: list[dict], config: V3Config) -> tuple[torch.Tensor, torch.Tensor]:
    if not examples:
        raise ValueError("at least one completion example is required")
    sequences: list[tuple[list[int], int]] = []
    for example in examples:
        prompt = encode_prompt(make_prompt(example))
        target = encode_completion(example["solution"])
        if len(prompt) + len(target) > config.block:
            raise ValueError(f"example {example['id']} exceeds context window")
        sequences.append((prompt + target, len(prompt)))

    max_length = max(len(sequence) - 1 for sequence, _ in sequences)
    inputs = torch.full((len(sequences), max_length), PAD_ID, dtype=torch.long)
    labels = torch.full((len(sequences), max_length), -100, dtype=torch.long)
    for row, (sequence, prompt_length) in enumerate(sequences):
        x = sequence[:-1]
        y = sequence[1:]
        inputs[row, :len(x)] = torch.tensor(x, dtype=torch.long)
        # A target is supervised only after all prompt tokens have been read.
        first_completion_label = prompt_length - 1
        labels[row, first_completion_label:first_completion_label + len(y) - first_completion_label] = torch.tensor(
            y[first_completion_label:], dtype=torch.long
        )
    return inputs, labels


class LunaMiniCoderV3(nn.Module):
    def __init__(self, config: V3Config | None = None):
        super().__init__()
        self.cfg = config or V3Config()
        if self.cfg.vocab != VOCAB_SIZE or self.cfg.block < 512:
            raise ValueError("V3 requires vocab 130 and a context window of at least 512")
        self.token = nn.Embedding(self.cfg.vocab, self.cfg.width)
        self.position = nn.Embedding(self.cfg.block, self.cfg.width)
        self.blocks = nn.ModuleList(CausalBlock(self.cfg) for _ in range(self.cfg.layers))
        self.norm = nn.LayerNorm(self.cfg.width)
        self.head = nn.Linear(self.cfg.width, self.cfg.vocab, bias=False)
        self.head.weight = self.token.weight

    def forward(self, inputs: torch.Tensor, labels: torch.Tensor | None = None):
        if inputs.ndim != 2 or inputs.shape[1] > self.cfg.block:
            raise ValueError("input shape exceeds V3 context window")
        positions = torch.arange(inputs.shape[1], device=inputs.device)
        hidden = self.token(inputs) + self.position(positions)
        for block in self.blocks:
            hidden = block(hidden)
        logits = self.head(self.norm(hidden))
        if labels is None:
            return logits, None
        if labels.shape != inputs.shape:
            raise ValueError("labels must match input shape")
        if not bool((labels != -100).any()):
            raise ValueError("batch contains no supervised completion tokens")
        loss = F.cross_entropy(
            logits.reshape(-1, self.cfg.vocab),
            labels.reshape(-1),
            ignore_index=-100,
        )
        return logits, loss

    @torch.inference_mode()
    def generate(self, prompt: str, *, max_new_tokens: int = 512) -> tuple[str, bool]:
        if not 1 <= max_new_tokens <= 2048:
            raise ValueError("max_new_tokens must be between 1 and 2048")
        encoded = encode_prompt(prompt)
        if len(encoded) >= self.cfg.block:
            raise ValueError("prompt must leave room within the V3 context window")
        self.eval()
        ids = torch.tensor([encoded], dtype=torch.long)
        generated: list[int] = []
        terminated = False
        for _ in range(max_new_tokens):
            context = ids[:, -self.cfg.block:]
            logits, _ = self(context)
            next_id = int(logits[:, -1, :].argmax(dim=-1).item())
            if next_id == EOS_ID:
                terminated = True
                break
            if next_id == PAD_ID:
                next_id = ord("?")
            generated.append(next_id)
            ids = torch.cat((ids, torch.tensor([[next_id]], dtype=torch.long)), dim=1)
        return bytes(generated).decode("ascii"), terminated

    def config_dict(self) -> dict:
        return asdict(self.cfg)
