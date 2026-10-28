"""Luna Forge Zero: trainable game-brief planner, no pretrained weights."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
import torch
from torch import nn

FEATURES = ("jump", "attack", "enemies", "coins", "dash", "health")
GENRES = ("platformer", "topdown")

def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text)

def make_vocab(sentences: list[str], limit: int = 2000) -> dict[str, int]:
    from collections import Counter
    counts = Counter(w for sentence in sentences for w in tokenize(sentence))
    return {w: n + 2 for n, (w, _) in enumerate(counts.most_common(limit - 2))} | {"<pad>": 0, "<unk>": 1}

def encode(text: str, vocab: dict[str, int], length: int = 48) -> list[int]:
    seq = [vocab.get(w, 1) for w in tokenize(text)][:length]
    return seq + [0] * (length - len(seq))

class LunaGamePlanner(nn.Module):
    """Embedding + mean/max pooling + MLP + game genre/features heads."""
    def __init__(self, vocab_size: int, dim: int = 48, hidden: int = 96):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, dim, padding_idx=0)
        self.net = nn.Sequential(nn.Linear(dim * 2, hidden), nn.GELU(), nn.Linear(hidden, hidden), nn.GELU())
        self.genre = nn.Linear(hidden, len(GENRES))
        self.features = nn.Linear(hidden, len(FEATURES))

    def forward(self, ids: torch.Tensor):
        mask = ids.ne(0).unsqueeze(-1)
        embedded = self.embed(ids)
        mean = (embedded * mask).sum(1) / mask.sum(1).clamp(min=1)
        maximum = embedded.masked_fill(~mask, -1e5).max(1).values
        maximum = torch.where(mask.any(1), maximum, torch.zeros_like(maximum))
        hidden = self.net(torch.cat([mean, maximum], dim=-1))
        return self.genre(hidden), self.features(hidden)

def load_model(folder: str | Path):
    root = Path(folder)
    vocab = json.loads((root / "vocab.json").read_text(encoding="utf-8"))
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    model = LunaGamePlanner(len(vocab), config["dim"], config["hidden"])
    model.load_state_dict(torch.load(root / "weights.pt", map_location="cpu", weights_only=True))
    model.eval()
    return model, vocab, config

@torch.inference_mode()
def predict(text: str, model: LunaGamePlanner, vocab: dict[str, int]) -> dict:
    x = torch.tensor([encode(text, vocab)])
    genre_logits, feat_logits = model(x)
    probabilities = torch.sigmoid(feat_logits[0]).tolist()
    return {
        "genre": GENRES[genre_logits[0].argmax().item()],
        "features": {name: p >= 0.5 for name, p in zip(FEATURES, probabilities)},
        "confidence": {name: round(p, 3) for name, p in zip(FEATURES, probabilities)},
        "genre_confidence": round(torch.softmax(genre_logits[0], 0).max().item(), 3),
    }
