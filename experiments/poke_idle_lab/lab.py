"""Comparador CSV local. Não acessa contas nem servidores dos jogos."""
import argparse
import csv
import json
from pathlib import Path

GAMES = {"world": "Poke Idle World", "io": "Poke Idle IO"}
IO_GEM_USD_INDICATIVE = 0.007  # taxa ANUNCIADA, não é prova de saque
FIELDS = ("minutes", "xp", "coins", "gems_received_net", "listings",
          "sales", "withdrawn_usd", "operating_cost_brl")


def read_sessions(path):
    sessions = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            row["game"] = row["game"].strip().lower()
            if row["game"] not in GAMES:
                raise ValueError("Jogo inválido")
            for key in FIELDS:
                row[key] = float(row[key])
                if row[key] < 0:
                    raise ValueError("Valores não podem ser negativos")
            if row["minutes"] <= 0:
                raise ValueError("Duração deve ser positiva")
            if row["sales"] > row["listings"]:
                raise ValueError("Vendas excedem anúncios")
            row["source"] = row.get("source", "real").strip().lower()
            sessions.append(row)
    return sessions


def summarize(rows):
    output = []
    for game, name in GAMES.items():
        subset = [r for r in rows if r["game"] == game]
        if not subset:
            continue
        hours = sum(r["minutes"] for r in subset) / 60
        gems = sum(r["gems_received_net"] for r in subset)
        # Nunca contar saques de sessões marcadas como demonstração.
        withdrawn = sum(r["withdrawn_usd"] for r in subset if r["source"] != "demo")
        output.append({
            "game": game, "name": name,
            "source": "DEMONSTRACAO" if any(r["source"] == "demo" for r in subset) else "REGISTRADO",
            "hours": round(hours, 3), "sessions": len(subset),
            "xp_per_hour": round(sum(r["xp"] for r in subset) / hours, 2),
            "coins_per_hour": round(sum(r["coins"] for r in subset) / hours, 2),
            "net_gems_per_hour": round(gems / hours, 2),
            "sales": int(sum(r["sales"] for r in subset)),
            "usd_actually_withdrawn": round(withdrawn, 2),
            "usd_withdrawn_per_hour": round(withdrawn / hours, 4),
            "io_gems_usd_indicative_NOT_WITHDRAWN": round(gems * IO_GEM_USD_INDICATIVE, 2) if game == "io" else None,
            "cost_brl": round(sum(r["operating_cost_brl"] for r in subset), 2)
        })
    return output


def format_report(rows):
    by_game = {r["game"]: r for r in rows}
    metrics = [
        ("source", "Fonte"), ("hours", "Horas"), ("xp_per_hour", "XP/h"),
        ("coins_per_hour", "Coins/h"), ("net_gems_per_hour", "Gemas liquidas/h"),
        ("sales", "Vendas"), ("usd_actually_withdrawn", "US$ efetivamente sacados"),
        ("usd_withdrawn_per_hour", "US$ sacados/h"),
        ("io_gems_usd_indicative_NOT_WITHDRAWN", "US$ indicativos NAO sacados"),
        ("cost_brl", "Custo operacional R$")]
    result = ["# Comparativo Poke Idle Lab", "",
              "Dados DEMONSTRACAO sao ficticios. Gemas nao sao saques.", "",
              "| Metrica | World | IO |", "|---|---:|---:|"]
    for key, label in metrics:
        def cell(game):
            val = by_game.get(game, {}).get(key)
            return "—" if val is None else str(val)
        result.append("| {} | {} | {} |".format(label, cell("world"), cell("io")))
    result.extend(["", "Rentabilidade exige saques confirmados e custos convertidos para a mesma moeda."])
    return "\n".join(result)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=Path)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = summarize(read_sessions(args.csv))
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else format_report(data))
