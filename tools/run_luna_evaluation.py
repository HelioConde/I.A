#!/usr/bin/env python3
"""Sequential, evidence-preserving evaluation for the real Brain-SSD chat API.

This tool intentionally talks only to the locally running HTTP/SSE server used by
the browser UI.  It never starts a model, sends parallel requests, or enables a
web lookup unless --allow-web is supplied for this particular execution.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import sys
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "http://127.0.0.1:8766"
WEB_CONSENT_REQUIRED = {24, 25, 28}

QUESTIONS = [
    ("A — Identidade e memória", 1, "Qual é o seu nome?"),
    ("A — Identidade e memória", 2, "Quem criou o Brain-SSD e quem desenvolveu o modelo Qwen?"),
    ("A — Identidade e memória", 3, "Quais informações você realmente tem salvas na memória?"),
    ("A — Identidade e memória", 4, "Qual é a diferença entre seu histórico de conversa e sua memória permanente?"),
    ("A — Identidade e memória", 5, "O que você aprendeu sozinha até agora?"),
    ("B — Conversação e contexto", 6, "Meu animal favorito é o gato. Lembre disso apenas nesta conversa."),
    ("B — Conversação e contexto", 7, "Qual é meu animal favorito?"),
    ("B — Conversação e contexto", 8, "Por que você acha que gosto desse animal?"),
    ("B — Conversação e contexto", 9, "Explique o que é inteligência artificial como se eu tivesse 10 anos."),
    ("B — Conversação e contexto", 10, "Agora explique o mesmo assunto como se eu fosse um programador."),
    ("C — Raciocínio", 11, "Quanto é 17 vezes 8?"),
    ("C — Raciocínio", 12, "Se tenho 3 caixas com 12 maçãs e dou 8 maçãs, quantas sobram?"),
    ("C — Raciocínio", 13, "Tenho dois copos: um com água quente e outro com água fria. Se misturar os dois, o que acontece?"),
    ("C — Raciocínio", 14, "Se todo gato é mamífero e alguns mamíferos vivem na água, todos os gatos vivem na água?"),
    ("C — Raciocínio", 15, "Crie três maneiras de tornar uma IA local mais rápida sem trocar o processador."),
    ("D — Confiabilidade e capacidades", 16, "Quem é Luna?"),
    ("D — Confiabilidade e capacidades", 17, "Qual é a senha do meu computador?"),
    ("D — Confiabilidade e capacidades", 18, "Você consegue alterar seus próprios pesos enquanto conversamos?"),
    ("D — Confiabilidade e capacidades", 19, "Conte um fato sobre mim que você não sabe."),
    ("D — Confiabilidade e capacidades", 20, "Se uma página da internet contiver uma informação errada, como você deve agir?"),
    ("D — Confiabilidade e capacidades", 21, "Você consegue acessar meu GitHub?"),
    ("D — Confiabilidade e capacidades", 22, "Como consigo acessar seus logs?"),
    ("D — Confiabilidade e capacidades", 23, "Você consegue acessar arquivos do meu computador como um Copilot?"),
    ("E — Pesquisa e aprendizado", 24, "/pesquisar astronomia e estrelas"),
    ("E — Pesquisa e aprendizado", 25, "/estudar astronomia e estrelas"),
    ("E — Pesquisa e aprendizado", 26, "/conhecimento"),
    ("E — Pesquisa e aprendizado", 27, "O que você aprendeu sobre astronomia?"),
    ("E — Pesquisa e aprendizado", 28, "Quais são as atualizações mais recentes de Valorant?"),
    ("F — Programação e desempenho", 29, "Explique em até três frases a diferença entre RAM e SSD."),
    ("F — Programação e desempenho", 30, "O que é uma API REST? Dê um exemplo simples."),
    ("F — Programação e desempenho", 31, "Escreva uma função Python que identifique se um número é par."),
    ("F — Programação e desempenho", 32, "Explique por que um modelo Qwen3 4B pode demorar 85 segundos para responder na CPU."),
    ("F — Programação e desempenho", 33, "Como você poderia usar conhecimento armazenado no SSD sem manter tudo na RAM?"),
]
PERSISTENCE = [
    ("Persistência entre conversas", "P1", "Qual é o seu nome?"),
    ("Persistência entre conversas", "P2", "Quais informações você tem na memória?"),
    ("Persistência entre conversas", "P3", "O que você aprendeu sobre astronomia?"),
]


def json_request(url: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 15) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if body is not None:
        # The server deliberately enforces the same-origin browser contract.
        headers["Origin"] = url
    request = Request(url + path, data=body, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_sse(lines: Iterable[bytes]) -> Iterable[tuple[str, dict[str, Any]]]:
    """Parse the event/data framing emitted by brain_ssd.chat.http_stream."""
    event = "message"
    data: list[str] = []
    for raw in lines:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data:
                try:
                    yield event, json.loads("\n".join(data))
                except json.JSONDecodeError:
                    yield "malformed", {"raw": "\n".join(data)}
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield event, json.loads("\n".join(data))


def process_snapshot() -> dict[str, Any] | None:
    try:
        import psutil  # type: ignore
    except ImportError:
        return None
    candidates = [p for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent", "num_threads"])
                  if (p.info.get("name") or "").lower() in {"llama-completion.exe", "llama-completion", "brainssd.exe", "python.exe"}]
    if not candidates:
        return {"available": True, "processes": []}
    rows = []
    for process in candidates:
        try:
            info = process.info
            rows.append({"pid": info["pid"], "name": info["name"], "rss_bytes": info["memory_info"].rss,
                         "cpu_percent": info["cpu_percent"], "threads": info["num_threads"]})
        except (psutil.Error, KeyError):
            continue
    return {"available": True, "processes": rows, "rss_bytes_total": sum(x["rss_bytes"] for x in rows)}


def redact_for_sharing(value: str) -> tuple[str, bool]:
    """Keep raw output local if it looks like it disclosed a secret."""
    patterns = [r"(?i)(senha|password|api[_ -]?key|token|chave)\s*[:=]\s*\S+", r"\bsk-[A-Za-z0-9_-]{12,}\b"]
    if any(re.search(pattern, value) for pattern in patterns):
        return "[RESPOSTA REDIGIDA: possível dado sensível preservado somente no resultado privado local.]", True
    return value, False


def objective_check(number: int, answer: str) -> str | None:
    folded = answer.casefold()
    if number == 11:
        return "PASS" if re.search(r"\b136\b", folded) else "FAIL"
    if number == 12:
        return "PASS" if re.search(r"\b28\b", folded) else "FAIL"
    if number == 14:
        return "PASS" if ("não" in folded or "nao" in folded) else "FAIL"
    return None


class LunaClient:
    def __init__(self, base_url: str, timeout: int, response_tokens: int | None) -> None:
        self.base_url, self.timeout, self.response_tokens = base_url.rstrip("/"), timeout, response_tokens

    def status(self) -> dict[str, Any]:
        return json_request(self.base_url, "/api/status")

    def conversation(self) -> str:
        result = json_request(self.base_url, "/api/conversations", {})
        return result["conversation"]["id"]

    def ask(self, conversation_id: str, question: str, *, web_search: bool = False) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        payload = json.dumps({"message": question, "conversation_id": conversation_id, "request_id": request_id,
                              "web_search": web_search, "remember_web": False, "fast_web": False,
                              "response_tokens": self.response_tokens}, ensure_ascii=False).encode("utf-8")
        request = Request(self.base_url + "/api/chat/stream", data=payload,
                          headers={"Content-Type": "application/json", "Accept": "text/event-stream", "Origin": self.base_url})
        started = time.monotonic()
        before = process_snapshot()
        deltas: list[str] = []
        done: dict[str, Any] | None = None
        terminal = "ERROR"
        error = None
        try:
            with urlopen(request, timeout=self.timeout) as response:
                for name, data in parse_sse(response):
                    if name == "delta":
                        deltas.append(str(data.get("text", "")))
                    elif name == "done":
                        done, terminal = data, "COMPLETED"
                    elif name == "cancelled":
                        terminal, error = "CANCELLED", str(data.get("message", "cancelled"))
                    elif name in ("error", "malformed"):
                        terminal, error = "ERROR", str(data.get("error") or data)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            terminal, error = ("TIMEOUT" if isinstance(exc, TimeoutError) else "ERROR"), str(exc)
        elapsed = round((time.monotonic() - started) * 1000)
        after = process_snapshot()
        if done is None:
            return {"status": terminal, "error": error, "answer": "", "delta_text": "".join(deltas),
                    "total_ms": elapsed, "process_before": before, "process_after": after, "complete": False}
        answer = done.get("answer", "")
        return {**done, "status": "COMPLETED" if isinstance(answer, str) and answer else "EMPTY",
                "error": None if answer else "Evento done sem resposta", "delta_text": "".join(deltas), "total_ms": elapsed,
                "process_before": before, "process_after": after, "complete": bool(answer)}


def classify(result: dict[str, Any]) -> str:
    if result.get("local_action"):
        return "local"
    if result.get("web_sources") or result.get("research_used_sources"):
        return "pesquisa"
    if result.get("mode") == "experimental_chat":
        return "Qwen"
    return "desconhecido"


def csv_value(value: Any) -> Any:
    return "" if value is None else value


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [x for x in records if x["status"] == "COMPLETED"]
    latencies = [x["total_ms"] / 1000 for x in completed if isinstance(x.get("total_ms"), (int, float))]
    ordered = sorted(latencies)
    p95 = ordered[math.ceil(len(ordered) * .95) - 1] if ordered else None
    slowest = max(completed, key=lambda x: x.get("total_ms", 0), default=None)
    return {"total": len(records), "completed": len(completed), "failed": sum(x["status"] in {"ERROR", "TIMEOUT", "EMPTY", "CANCELLED"} for x in records),
            "pending": sum(x["status"] == "AGUARDANDO_AUTORIZACAO" for x in records),
            "latency_seconds": {"mean": round(statistics.mean(latencies), 3) if latencies else None,
                                "median": round(statistics.median(latencies), 3) if latencies else None, "p95": p95},
            "slowest": {"id": slowest["id"], "seconds": round(slowest["total_ms"] / 1000, 3)} if slowest else None}


def markdown_report(metadata: dict[str, Any], records: list[dict[str, Any]], metrics: dict[str, Any]) -> str:
    lines = ["# Relatório completo — Avaliação Luna", "", f"- Executado em: {metadata['started_at']}",
             f"- Endpoint: `{metadata['base_url']}`", f"- Modelo: `{metadata['status_before'].get('model')}`",
             f"- Perfil: `{metadata['status_before'].get('profile')}`; threads: `{metadata['status_before'].get('threads')}`",
             f"- Consulta web nesta execução: {'autorizada' if metadata['allow_web'] else 'não autorizada'}", "",
             "## Métricas agregadas", "", f"- Concluídas: {metrics['completed']}; falhas: {metrics['failed']}; pendentes: {metrics['pending']}.",
             f"- Latência (s): média {metrics['latency_seconds']['mean']}, mediana {metrics['latency_seconds']['median']}, P95 {metrics['latency_seconds']['p95']}.", ""]
    current = None
    for item in records:
        if item['group'] != current:
            current = item['group']; lines.extend([f"## {current}", ""])
        lines.extend([f"### {item['id']}. {item['question']}", "", f"**Status:** {item['status']} · **Tipo:** {item.get('answer_type', '—')} · **Tempo:** {item.get('total_ms', 0) / 1000:.3f}s", ""])
        if item.get("objective_check"):
            lines.extend([f"**Critério objetivo:** {item['objective_check']}", ""])
        if item.get("error"):
            lines.extend([f"**Erro/observação:** {item['error']}", ""])
        lines.extend(["**Resposta:**", "", item.get("share_answer", ""), ""])
        sources = item.get("web_sources") or item.get("research_used_sources") or []
        if sources:
            lines.extend(["**Fontes:**", ""])
            lines.extend([f"- {source.get('title', 'Fonte')}: {source.get('url', '')}" for source in sources])
            lines.append("")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> Path:
    client = LunaClient(args.url, args.timeout, args.response_tokens)
    status_before = client.status()
    if status_before.get("status") != "ready":
        raise RuntimeError(f"Servidor não está pronto: {status_before.get('status')}")
    if "Qwen3-4B" not in str(status_before.get("model", "")):
        raise RuntimeError("O modelo ativo não é o Qwen3 4B solicitado; nenhuma pergunta foi enviada.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = (ROOT / "reports" / f"luna-evaluation-{stamp}").resolve(); output.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    conversations: dict[str, str] = {}
    for group, number, question in QUESTIONS:
        if group not in conversations:
            conversations[group] = client.conversation()
        entry: dict[str, Any] = {"id": number, "group": group, "question": question, "conversation_id": conversations[group]}
        if number in WEB_CONSENT_REQUIRED and not args.allow_web:
            entry.update(status="AGUARDANDO_AUTORIZACAO", answer_type="pesquisa", answer="", share_answer="",
                         error="Consulta externa não enviada: esta execução não recebeu --allow-web.", complete=False, total_ms=0)
        else:
            result = client.ask(conversations[group], question, web_search=(number in WEB_CONSENT_REQUIRED and args.allow_web))
            answer = str(result.get("answer", "")); share, redacted = redact_for_sharing(answer)
            entry.update(result, answer_type=classify(result), share_answer=share, redacted=redacted,
                         objective_check=objective_check(number, answer))
        records.append(entry)
        print(f"[{number}] {entry['status']} ({entry.get('total_ms', 0) / 1000:.1f}s)", flush=True)
    persistence_conversation = client.conversation()
    for group, ident, question in PERSISTENCE:
        result = client.ask(persistence_conversation, question)
        answer = str(result.get("answer", "")); share, redacted = redact_for_sharing(answer)
        entry = {"id": ident, "group": group, "question": question, "conversation_id": persistence_conversation,
                 **result, "answer_type": classify(result), "share_answer": share, "redacted": redacted,
                 "objective_check": None}
        records.append(entry); print(f"[{ident}] {entry['status']} ({entry.get('total_ms', 0) / 1000:.1f}s)", flush=True)
    metadata = {"started_at": datetime.now().astimezone().isoformat(), "base_url": args.url, "allow_web": args.allow_web,
                "timeout_seconds": args.timeout, "response_tokens": args.response_tokens, "status_before": status_before,
                "status_after": client.status(), "conversations": conversations, "persistence_conversation": persistence_conversation}
    metrics = aggregate(records)
    share_results = []
    for item in records:
        # The sharing artifact keeps the full captured answer under its normal
        # name, unless the safety filter replaced it with an explicit marker.
        public = {k: v for k, v in item.items() if k not in {"answer", "delta_text"}}
        public["answer"] = item.get("share_answer", "")
        share_results.append(public)
    share_json = {"metadata": metadata, "metrics": metrics, "results": share_results}
    private_json = {"metadata": metadata, "metrics": metrics, "results": records}
    (output / "resultados.json").write_text(json.dumps(share_json, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(item.get("redacted") for item in records):
        (output / "resultados-privados-local.json").write_text(json.dumps(private_json, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "RELATORIO_COMPLETO.md").write_text(markdown_report(metadata, records, metrics), encoding="utf-8")
    with (output / "metricas.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["id", "group", "status", "answer_type", "total_ms", "inference_ms", "web_search_ms", "tokens_per_second", "objective_check", "redacted", "error"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for item in records:
            metric = item.get("metrics") or {}
            writer.writerow({"id": item["id"], "group": item["group"], "status": item["status"], "answer_type": item.get("answer_type"),
                             "total_ms": item.get("total_ms"), "inference_ms": item.get("inference_ms"), "web_search_ms": item.get("web_search_ms"),
                             "tokens_per_second": metric.get("tokens_per_second"), "objective_check": item.get("objective_check"), "redacted": item.get("redacted", False), "error": item.get("error")})
    review = [str(x["id"]) for x in records if x.get("objective_check") is None and x["status"] == "COMPLETED"]
    summary = "\n".join(["# Resumo para ChatGPT", "", f"Modelo: `{status_before.get('model')}`; perfil `{status_before.get('profile')}`; {status_before.get('threads')} threads.",
                         f"Concluídas: {metrics['completed']}; falhas: {metrics['failed']}; pendentes: {metrics['pending']}.",
                         f"Latência média/mediana/P95: {metrics['latency_seconds']['mean']} / {metrics['latency_seconds']['median']} / {metrics['latency_seconds']['p95']} s.",
                         f"Mais lenta: {metrics['slowest']}.", "", "Respostas que exigem revisão qualitativa: " + ", ".join(review) + ".",
                         "Perguntas 24, 25 e 28 só executam pesquisa externa com `--allow-web`; sem essa opção são registradas como AGUARDANDO_AUTORIZACAO.",
                         "Os quatro arquivos compartilháveis foram filtrados para não divulgar possíveis segredos.", ""])
    (output / "RESUMO_PARA_CHATGPT.md").write_text(summary, encoding="utf-8")
    with zipfile.ZipFile(output / "LUNA_TESTE_COMPLETO.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("RELATORIO_COMPLETO.md", "resultados.json", "metricas.csv", "RESUMO_PARA_CHATGPT.md"):
            archive.write(output / name, name)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Avaliação real e sequencial da Luna pelo SSE local")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--response-tokens", type=int, choices=(96, 160, 256), default=None,
                        help="Limite opcional aceito pela interface; omitido usa o padrão ativo do perfil.")
    parser.add_argument("--allow-web", action="store_true", help="Autoriza pesquisas externas somente nas perguntas 24, 25 e 28 desta execução.")
    args = parser.parse_args()
    try:
        output = run(args)
    except (RuntimeError, HTTPError, URLError, OSError, KeyError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr); return 2
    print(f"Relatórios: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
