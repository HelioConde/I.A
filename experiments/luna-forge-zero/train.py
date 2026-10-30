"""Deterministic synthetic training for Luna Game Planner (no pretrained weights)."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from luna_model import FEATURES, GENRES, LunaGamePlanner, encode, make_vocab

GENRE_PHRASES = {
    "platformer": ("plataforma 2d", "jogo de plataforma", "aventura de plataformas", "plataformas laterais", "jogo de pular plataformas", "jogo de plataformas", "plataformas", "plataforma", "um platformer", "jogo estilo plataforma", "jogo de parkour", "jogo de aventura lateral"),
    "topdown": ("visao de cima", "jogo top down", "arena vista de cima", "jogo com camera superior", "aventura topdown", "rpg visto de cima", "jogo visto de cima", "jogo top-down", "arena topdown", "rpg top down", "jogo com camera vista de cima"),
}
FEATURE_PHRASES = {
    "jump": ("pulos", "saltar", "pular", "mecanica de salto", "personagem que pula", "com pulo", "pulo", "saltos", "salto", "pular mais alto", "sistema de pulo"),
    "attack": ("combate", "ataques", "golpes de espada", "bater nos adversarios", "mecanica de atacar", "ataque corpo a corpo", "espada", "atacar monstros", "batalho com monstros", "batalhas", "golpear", "luta", "sistema de combate"),
    "enemies": ("inimigos", "monstros", "criaturas hostis", "adversarios", "oponentes", "ameacas que perseguem", "monstros inimigos", "enfrentando criaturas hostis", "vilões", "chefes inimigos"),
    "coins": ("moedas para coletar", "coletar cristais", "itens para pegar", "gemas colecionaveis", "recolher moedas", "colecionar tesouros", "moedas", "cristais colecionaveis", "coletando moedas", "coleto gemas", "pegar moedas", "moedas brilhantes", "coleta de gemas"),
    "dash": ("dash", "esquiva rapida", "impulso veloz", "corrida curta", "arrancada veloz", "movimento de dash", "esquivar", "correr rapidamente"),
    "health": ("barra de vida", "pontos de vida", "coracoes de energia", "sistema de saude", "indicador de vida", "vida do personagem", "coracoes de vida", "vida", "saude", "indicador de saude"),
}
INTRO = ("Crie um", "Quero um", "Faca um", "Desenvolva um", "Construa um", "Preciso de um", "Projete um", "Faz uma", "Fazer uma", "Um", "Construir", "Quero", "Crie", "Desenvolva uma", "Quero criar um")
JOIN = (" com ", " incluindo ", " que tenha ", " contendo ", " onde tem ", " onde posso ", " com o personagem usando ", ", preciso de ", " de ")
AND = (", ", " e ", " mais ", " junto com ", ", tambem ", ", onde tenha ", ", alem de ", " e faco ")

def sample(rng: random.Random):
    genre = rng.choice(GENRES)
    flags = [rng.random() < 0.52 for _ in FEATURES]
    if not any(flags):
        flags[rng.randrange(len(FEATURES))] = True
    pieces = [rng.choice(FEATURE_PHRASES[name]) for name, enabled in zip(FEATURES, flags) if enabled]
    rng.shuffle(pieces)
    prompt = rng.choice(INTRO) + " " + rng.choice(GENRE_PHRASES[genre]) + rng.choice(JOIN) + pieces[0]
    for part in pieces[1:]:
        prompt += rng.choice(AND) + part
    prompt += rng.choice((".", "!", ".", " para computador.", " em pixel art."))
    return prompt, GENRES.index(genre), [float(v) for v in flags]

def make_splits(seed, train_size, val_size, test_size):
    rng = random.Random(seed)
    seen = set()
    splits = []
    for n in (train_size, val_size, test_size):
        split = []
        while len(split) < n:
            row = sample(rng)
            if row[0] not in seen:
                seen.add(row[0])
                split.append(row)
        splits.append(split)
    return splits

def evaluate(model, loader):
    model.eval()
    totals = dict(samples=0, genres=0, feature_correct=0, features=0, exact=0, loss=0.0)
    with torch.no_grad():
        for ids, g, f in loader:
            gl, fl = model(ids)
            pred_g = gl.argmax(1)
            pred_f = torch.sigmoid(fl) >= 0.5
            correct_f = pred_f == f.bool()
            n = len(ids)
            totals["samples"] += n
            totals["genres"] += int((pred_g == g).sum())
            totals["feature_correct"] += int(correct_f.sum())
            totals["features"] += correct_f.numel()
            totals["exact"] += int(((pred_g == g) & correct_f.all(1)).sum())
            totals["loss"] += float((nn.functional.cross_entropy(gl, g) + nn.functional.binary_cross_entropy_with_logits(fl, f))) * n
    n = totals["samples"]
    return {"samples": n, "genre_accuracy": round(totals["genres"] / n, 4),
            "feature_accuracy": round(totals["feature_correct"] / totals["features"], 4),
            "exact_match": round(totals["exact"] / n, 4), "loss": round(totals["loss"] / n, 4)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="checkpoints/luna-forge-zero-v0")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--train-size", type=int, default=9000)
    ap.add_argument("--val-size", type=int, default=600)
    ap.add_argument("--test-size", type=int, default=600)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    train, val, test = make_splits(args.seed, args.train_size, args.val_size, args.test_size)
    vocab = make_vocab([x[0] for x in train])
    config = {"dim": 48, "hidden": 96, "seed": args.seed, "architecture": "original-embedding-pool-mlp", "tokenizer": "unicode-word-v1", "features": FEATURES, "genres": GENRES}

    def loader(rows, shuffle=False):
        x = torch.tensor([encode(s, vocab) for s, _, _ in rows], dtype=torch.long)
        g = torch.tensor([g for _, g, _ in rows], dtype=torch.long)
        f = torch.tensor([f for _, _, f in rows], dtype=torch.float32)
        return DataLoader(TensorDataset(x, g, f), batch_size=args.batch_size, shuffle=shuffle)

    model = LunaGamePlanner(len(vocab), config["dim"], config["hidden"])
    opt = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.01)
    best = -1.0
    best_state = None
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        for x, genre, flags in loader(train, shuffle=True):
            lg, lf = model(x)
            loss = nn.functional.cross_entropy(lg, genre) + nn.functional.binary_cross_entropy_with_logits(lf, flags)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        metrics = evaluate(model, loader(val))
        history.append({"epoch": epoch, **metrics})
        print(f"epoch {epoch:02d} val exact={metrics['exact_match']:.3f} feature={metrics['feature_accuracy']:.3f} loss={metrics['loss']:.3f}", flush=True)
        if metrics["exact_match"] > best:
            best = metrics["exact_match"]
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    test_result = evaluate(model, loader(test))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "weights.pt")
    (out / "vocab.json").write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"origin": "random initialization, no pretrained model", "training": "procedural Portuguese game-brief instructions", "train_samples": len(train), "val_samples": len(val), "test_samples": len(test), "split_isolation": "exact prompt strings deduplicated across sets", "parameter_count": sum(p.numel() for p in model.parameters()), "test": test_result, "best_validation_exact": best, "history": history, "limitations": "Only classifies 2 genres and 6 mechanics; game code comes from deterministic templates; test is synthetic."}
    summary["weights_sha256"] = hashlib.sha256((out / "weights.pt").read_bytes()).hexdigest()
    (out / "report.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="history"}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
