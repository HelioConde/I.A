"""Heurística de hunts sem ações no jogo. Entradas são estimativas fornecidas pelo usuário."""
import argparse
import csv


def rank_hunts(rows):
    choices = []
    for row in rows:
        xp = float(row["xp_per_hour"])
        gems = float(row["estimated_gems_per_hour"])
        risk = float(row["failure_probability"])
        confidence = float(row["confidence"])
        if xp < 0 or gems < 0 or not 0 <= risk <= 1 or not 0 <= confidence <= 1:
            raise ValueError("XP/gemas >=0 e risco/confianca entre 0 e 1")
        # Pontuação experimental, NAO e previsão de dinheiro.
        score = (xp / 1000 + gems * 10) * (1 - risk) * confidence
        choices.append((round(score, 4), row["game"], row["hunt"]))
    return sorted(choices, reverse=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as file:
        for score, game, hunt in rank_hunts(list(csv.DictReader(file))):
            print("{}: {} ({})".format(game, hunt, score))
