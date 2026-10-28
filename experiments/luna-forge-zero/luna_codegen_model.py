"""Small decoder-only autoregressive Transformer for original code-generation research."""
from __future__ import annotations
from dataclasses import dataclass
import torch
from torch import nn
from torch.nn import functional as F

@dataclass
class Config:
    vocab: int = 128
    block: int = 128
    width: int = 64
    heads: int = 4
    layers: int = 2

class CausalBlock(nn.Module):
    def __init__(self, cfg: Config):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.width)
        self.qkv = nn.Linear(cfg.width, 3 * cfg.width)
        self.proj = nn.Linear(cfg.width, cfg.width)
        self.ln2 = nn.LayerNorm(cfg.width)
        self.ff = nn.Sequential(nn.Linear(cfg.width, 4 * cfg.width), nn.GELU(),
                                nn.Linear(4 * cfg.width, cfg.width))
        self.heads = cfg.heads

    def forward(self, x):
        b, t, c = x.shape
        q, k, v = self.qkv(self.ln1(x)).chunk(3, dim=-1)
        q = q.reshape(b, t, self.heads, c // self.heads).transpose(1, 2)
        k = k.reshape(b, t, self.heads, c // self.heads).transpose(1, 2)
        v = v.reshape(b, t, self.heads, c // self.heads).transpose(1, 2)
        att = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.proj(att.transpose(1, 2).reshape(b, t, c))
        return x + self.ff(self.ln2(x))

class LunaMiniCoder(nn.Module):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.token = nn.Embedding(cfg.vocab, cfg.width)
        self.position = nn.Embedding(cfg.block, cfg.width)
        self.blocks = nn.ModuleList([CausalBlock(cfg) for _ in range(cfg.layers)])
        self.norm = nn.LayerNorm(cfg.width)
        self.head = nn.Linear(cfg.width, cfg.vocab, bias=False)
        self.head.weight = self.token.weight

    def forward(self, idx, targets=None):
        _, seq = idx.shape
        if seq > self.cfg.block:
            raise ValueError("Sequence exceeds context window")
        pos = torch.arange(seq, device=idx.device)
        x = self.token(idx) + self.position(pos)
        for block in self.blocks:
            x = block(x)
        logits = self.head(self.norm(x))
        if targets is None:
            return logits, None
        loss = F.cross_entropy(logits.reshape(-1, self.cfg.vocab), targets.reshape(-1))
        return logits, loss

    @torch.inference_mode()
    def generate(self, prompt: str, chars: int = 200, temperature: float = 0.75):
        self.eval()
        ids = torch.tensor([[ord(c) if ord(c) < 128 else ord("?") for c in prompt]], dtype=torch.long)
        if not 0 <= temperature <= 3:
            raise ValueError("Temperature must be 0 (greedy) or within (0, 3]")
        if not 1 <= chars <= 2048:
            raise ValueError("Output budget must be 1..2048 characters")
        for _ in range(chars):
            logits, _ = self(ids[:, -self.cfg.block:])
            logits = logits[:, -1, :]
            logits[:, 0:9] = -1e5
            if temperature == 0:
                # Reproducible diagnostic, without stochastic token sampling.
                nxt = torch.argmax(logits, dim=-1, keepdim=True)
            else:
                probs = torch.softmax(logits / temperature, dim=-1)
                nxt = torch.multinomial(probs, num_samples=1)
            ids = torch.cat((ids, nxt), dim=1)
            text = "".join(chr(i) for i in ids[0].tolist())
            continuation = text[len(prompt):]
            if "\nFIM" in continuation or "\nEND\n" in continuation:
                break
        return "".join(chr(i) for i in ids[0].tolist())
