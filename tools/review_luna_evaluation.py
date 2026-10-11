"""Audit Codex Luna benchmark completeness, without contacting internet or model."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.completion_quality import classify_completion


def assess_report(data: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError("O JSON deve conter uma lista results.")
    before = (data.get("metadata") or {}).get("status_before") or {}
    base = before.get("max_output_tokens") or 112
    base = base if type(base) is int and 1 <= base <= 2048 else 112
    items = []
    for row in data["results"]:
        if not isinstance(row, dict):
            continue
        item = {"id": row.get("id"), "question": str(row.get("question", ""))[:150],
                "request_status": row.get("status"), "answer_type": row.get("answer_type")}
        if row.get("status") != "COMPLETED":
            item["quality_status"] = "not_executed"
        elif row.get("mode") == "local_command" or row.get("answer_type") == "local":
            item["quality_status"] = "local_action_not_inference"
        else:
            metric = row.get("metrics") or {}
            limit = row.get("generation_limit") or base
            limit = limit if type(limit) is int and limit > 0 else base
            finish = row.get("native_finish_reason")
            if finish is None and row.get("finish_reason") in ("length", "stop", "eos_token"):
                finish = row.get("finish_reason")
            result = classify_completion(
                str(row.get("share_answer") or row.get("answer") or ""),
                max_tokens=limit,
                generated_tokens=(row.get("generated_tokens") if type(row.get("generated_tokens")) is int
                                  else metric.get("generated_tokens")),
                finish_reason=finish,
            )
            item["quality_status"] = row.get("generation_status") or result["status"]
            item["answer_complete"] = row.get("answer_complete", result["answer_complete"])
            item["should_review"] = bool(
                row.get("needs_continuation", result["needs_continuation"])
                or item["quality_status"] in ("unverified", "suspected_truncated", "truncated")
            )
        items.append(item)
    return {"model": before.get("model"), "total": len(items),
            "verified_complete": sum(r.get("answer_complete") is True for r in items),
            "definitely_incomplete": sum(r.get("answer_complete") is False for r in items),
            "needs_review": sum(bool(r.get("should_review")) for r in items),
            "results": items}


def render_summary(review: dict) -> str:
    lines = ["# Auditoria de completude — Brain-SSD", "",
             f"Modelo: {review.get('model') or 'não informado'}",
             f"Respostas: {review['total']}",
             f"Completude confirmada pelo backend: {review['verified_complete']}",
             f"Completude negada pelo backend: {review['definitely_incomplete']}",
             f"Gerações que exigem revisão: {review['needs_review']}", "",
             "Uma requisição HTTP/SSE concluída não comprova que o conteúdo terminou. "
             "Sem motivo nativo de parada, a conclusão pode ser incerta.", "",
             "| Questão | Requisição | Qualidade textual |", "|---|---|---|"]
    for r in review["results"]:
        lines.append(f"| {r['id']} | {r['request_status']} | {r['quality_status']} |")
    lines += ["", "## Revisão necessária", ""]
    for r in review["results"]:
        if r.get("should_review"):
            lines.append(f"- {r['id']}: {r['question']} ({r['quality_status']})")
    return "\n".join(lines) + "\n"


def locate_results(requested: Path | None, *, root: Path = ROOT) -> Path:
    """Find the most recent Codex results without guessing a timestamped folder.

    An explicit real file wins. A copied instructional placeholder is not a
    path; use discovery instead. Never mutate the original benchmark JSON.
    """
    if requested is not None:
        if requested.is_file():
            return requested.resolve()
        if "CAMINHO_DO_RELATORIO" not in str(requested).upper():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {requested}\n"
                'Localize com: dir /s /b resultados.json\n'
                'Ou execute sem caminho: py -3 .\\tools\\review_luna_evaluation.py'
            )
    candidates = []
    for folder in (root / "reports", root / "relatorios", root):
        if not folder.is_dir():
            continue
        candidates.extend(folder.glob("resultados.json"))
        # Do not crawl model files or the entire disk. Only report folders.
        if folder != root:
            candidates.extend(folder.glob("*/resultados.json"))
            candidates.extend(folder.glob("*/*/resultados.json"))
    candidates = [p for p in set(candidates) if p.is_file()]
    if not candidates:
        raise FileNotFoundError(
            "Não encontrei resultados.json nas pastas reports/ ou relatorios/ "
            "do Brain-SSD.\n"
            "No CMD, execute: dir /s /b resultados.json\n"
            "Depois passe o caminho real entre aspas."
        )
    return max(candidates, key=lambda p: p.stat().st_mtime).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auditar respostas sem executar Qwen.")
    parser.add_argument("results", nargs="?", type=Path,
                        help="Caminho para resultados.json (opcional: usa o mais recente em reports/).")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        input_file = locate_results(args.results)
        data = json.loads(input_file.read_text(encoding="utf-8-sig"))
        review = assess_report(data)
        target = args.output or input_file.parent / "AUDITORIA_COMPLETUDE.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_summary(review), encoding="utf-8")
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"Erro na auditoria: {exc}", file=sys.stderr)
        return 2
    print(f"Relatório analisado: {input_file}")
    print(f"Auditoria gerada: {target}")
    print(f"{review['needs_review']} respostas precisam de revisão. Relatório original preservado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
