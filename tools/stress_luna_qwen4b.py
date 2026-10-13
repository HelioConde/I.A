#!/usr/bin/env python3
"""Long-running, opt-in Qwen3-4B Q8_0 stress test for Luna on Windows.

No downloads, no edits to GGUF/LUNA.ini, no screen/audio capture, and no
internet/tool use. Real inference runs in a supervised separate process.
--simulate exercises the report/turn machinery without pretending to run Qwen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from brain_ssd.chat.performance import windows_memory
from test_luna_models import CANDIDATE, CANDIDATE_SHA256
from usar_qwen4b_luna import verified_4b

PROMPTS = (
    "Responda em portugues brasileiro: quanto e 19 vezes 23? Explique o calculo brevemente.",
    "Explique em duas frases o que e cache LRU e quando ele ajuda.",
    "Escreva uma funcao Python que soma uma lista de inteiros e explique em uma frase.",
    "Um cliente pede um resumo de 3 linhas sobre memoria SSD. Escreva o resumo.",
    "Explique a diferenca entre memoria RAM e armazenamento SSD em linguagem simples.",
    "Se eu disser que voce abriu meu navegador, mas voce nao abriu, como responder corretamente?",
    "Responda de forma natural, como em uma chamada de voz: o que faz uma CPU?",
    "Quanto e 144 dividido por 12? Mostre o raciocinio em poucas palavras.",
    "Explique como evitar eco quando um assistente fala e escuta alternadamente.",
    "Escreva um exemplo curto de teste unitario Python com unittest.",
    "O que significa preservar o contexto de uma conversa entre turnos?",
    "Resuma em duas frases o motivo de testar varias vezes o uso de memoria.",
)

def utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def turn_prompt(index: int) -> str:
    # A fixed and reusable corpus; sequence varies across 24+ turns.
    return PROMPTS[index % len(PROMPTS)]

def summarize_turn(index: int, prompt: str, result: dict, elapsed: float,
                   *, inference_verified: bool) -> dict:
    answer = str(result.get("answer") or "").strip()
    if not answer or result.get("mode") == "local_command" or not inference_verified:
        raise RuntimeError(
            f"Turno {index + 1}: resposta vazia, rota local ou inferencia nao confirmada"
        )
    if len(answer) > 20000:
        raise RuntimeError(f"Turno {index + 1}: resposta anormalmente longa")
    return {
        "turn": index + 1, "elapsed_seconds": round(elapsed, 3),
        "prompt_id": index % len(PROMPTS), "answer_chars": len(answer),
        "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "answer_preview": answer[:350],
        "reported_generated_tokens": result.get("generated_tokens"),
        "answer_complete": result.get("answer_complete"),
        "completion": result.get("completion"),
        "mode": result.get("mode"),
    }

def append_event(destination: Path, data: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as output:
        output.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")
        output.flush()
        os.fsync(output.fileno())

def load_events(destination: Path) -> list[dict]:
    if not destination.is_file():
        return []
    events = []
    for line in destination.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                events.append(item)
        except (ValueError, TypeError):
            # A child process can be interrupted halfway through a line.
            continue
    return events

class SimulatedEngine:
    """Deliberately not a language model: used only to test pipeline overhead."""
    def __init__(self):
        self.closed = False
    def start(self):
        return None
    def status(self):
        return {"status":"ready", "inference_verified":True}
    def ask(self, question, history, **kwargs):
        return {"answer":"SIMULACAO: esta resposta foi produzida pelo teste, nao pelo Qwen.",
                "mode":"model", "generated_tokens":10, "answer_complete":True}
    def close(self):
        self.closed = True

def run_turns(engine, *, turns: int, tokens: int, event_path: Path,
              simulated: bool = False) -> list[dict]:
    results = []
    history: list[dict] = []
    for index in range(turns):
        prompt = turn_prompt(index)
        append_event(event_path, {"event":"turn_start","turn":index + 1,
                                  "utc":utc()})
        started = time.perf_counter()
        answer = engine.ask(prompt, history, response_tokens=tokens, web_search=False)
        elapsed = time.perf_counter() - started
        result = summarize_turn(index, prompt, answer, elapsed,
                                inference_verified=bool(engine.status().get("inference_verified")))
        result["simulated"] = simulated
        append_event(event_path, {"event":"turn_result", **result})
        results.append(result)
        # Fixed bound prevents quadratic context growth or unbounded local retention.
        history.extend(({"role":"user","content":prompt},
                        {"role":"assistant","content":str(answer["answer"])[:500]}))
        history = history[-6:]
    return results

def require_model() -> dict:
    if os.name != "nt":
        raise OSError("Inferencia pesada do Qwen3-4B: execute no Windows.")
    target = ROOT / "models" / CANDIDATE
    good, message = verified_4b(ROOT / "models")
    if not good:
        raise ValueError(message)
    available = windows_memory()
    if available is None or available.available < 6 * 1024 ** 3:
        raise ValueError(
            "Para proteger o computador, sao necessarios pelo menos 6 GiB "
            "de RAM fisica disponivel. Feche outros programas e tente novamente."
        )
    return {"model":CANDIDATE,"model_sha256":CANDIDATE_SHA256,  # already verified in verified_4b()
            "model_bytes":target.stat().st_size,
            "memory_available_start_bytes":available.available,
            "memory_total_bytes":available.total}

def worker(event_path: Path, turns: int, tokens: int, mode: str) -> int:
    from brain_ssd.chat.runtime import LocalChatRuntime
    from brain_ssd.chat.server import ChatEngine
    engine = ChatEngine(lambda: LocalChatRuntime(
        ROOT, profile="equilibrado", core_mode=mode, model_file=CANDIDATE
    ))
    try:
        engine.start()
        status = engine.status()
        if status.get("status") != "ready":
            raise RuntimeError("ChatEngine nao ficou pronto para inferencia.")
        append_event(event_path, {"event":"engine_ready","utc":utc(),
                                  "core_mode":status.get("core_mode"),
                                  "model":status.get("model")})
        results = run_turns(engine, turns=turns, tokens=tokens, event_path=event_path)
        append_event(event_path, {"event":"completed","count":len(results),"utc":utc()})
        return 0
    except Exception as exc:
        append_event(event_path, {"event":"failed", "exception":type(exc).__name__,
                                  "reason":str(exc)[:350],"utc":utc()})
        return 2
    finally:
        engine.close()

def collect_memory(pid: int) -> dict:
    """Optional process-tree RSS, not equal to physical SSD I/O or VRAM."""
    try:
        import psutil
    except ImportError:
        return {"tree_rss_bytes":None,"process_count":None}
    try:
        parent = psutil.Process(pid)
        family = [parent] + parent.children(recursive=True)
        total = 0
        count = 0
        for proc in family:
            try:
                total += proc.memory_info().rss
                count += 1
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
        return {"tree_rss_bytes":total if count else None,"process_count":count}
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"tree_rss_bytes":None,"process_count":None}

def terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill","/T","/F","/PID",str(process.pid)],
                       check=False, capture_output=True, timeout=15)
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass

def save_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                    default=str) + "\n", encoding="utf-8")
    temporary.replace(path)

def supervise(*, report_path: Path, turns: int, tokens: int, mode: str,
              max_minutes: int, per_turn_seconds: int) -> dict:
    events_path = report_path.with_suffix(".events.jsonl")
    if events_path.exists():
        raise FileExistsError(
            "Relatorio anterior existe: " + str(events_path) +
            ". Escolha outro --output para nao sobrescrever evidencias."
        )
    evidence = require_model()
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--events",str(events_path),"--turns",str(turns),
               "--tokens",str(tokens),"--core-mode",mode]
    started = time.monotonic()
    report = {"schema":1,"kind":"luna_qwen4b_heavy_stress",
              "status":"running","utc":utc(),"real_inference":True,
              "conditions":{"turns_requested":turns,"tokens_limit":tokens,
                            "mode":mode,"max_minutes":max_minutes,
                            "per_turn_seconds":per_turn_seconds,
                            "web":False,"copilot":False,"voice":False,
                            "cache_state":"uncontrolled"},
              "evidence":evidence,"results":[]}
    save_report(report_path, report)
    peak_rss = None
    low_ram_abort = False
    cause = None
    print(f"Iniciando teste real: {turns} turnos, modelo {CANDIDATE}. "
          "Nenhuma busca web, chamada de ferramentas ou microfone.",flush=True)
    with subprocess.Popen(command, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, cwd=ROOT,
                          shell=False) as process:
        last_turn = 0
        last_reported = 0
        last_start = time.monotonic()
        observed_start = False
        while process.poll() is None:
            entries = load_events(events_path)
            starts = [e for e in entries if e.get("event") == "turn_start"]
            finishes = [e for e in entries if e.get("event") == "turn_result"]
            if len(finishes) > last_reported:
                last_reported = len(finishes)
                latest = finishes[-1]
                print(f"Turnos reais: {last_reported}/{turns} | "
                      f"ultimo: {latest.get('elapsed_seconds')}s", flush=True)
            if len(starts) > last_turn:
                last_turn = len(starts)
                last_start = time.monotonic()
                observed_start = True
            measured = collect_memory(process.pid)
            if measured["tree_rss_bytes"] is not None:
                peak_rss = max(peak_rss or 0, measured["tree_rss_bytes"])
            system = windows_memory()
            if system and system.available < int(1.5 * 1024 ** 3):
                low_ram_abort = True
                cause = "RAM fisica disponivel abaixo de 1.5 GiB"
            if time.monotonic() - started > max_minutes * 60:
                cause = "Tempo total excedido"
            if time.monotonic() - last_start > per_turn_seconds:
                cause = ("Tempo de inicializacao excedido" if not observed_start
                         else "Tempo de um turno excedido")
            if cause:
                terminate_tree(process)
                break
            time.sleep(1)
        exit_code = process.wait(timeout=15)
    entries = load_events(events_path)
    results = [{k:v for k,v in item.items() if k != "event"}
               for item in entries if item.get("event") == "turn_result"]
    fail = next((e for e in entries if e.get("event") == "failed"), None)
    completed = any(e.get("event") == "completed" and
                    e.get("count") == turns for e in entries)
    report.update({
        "status":"passed" if not cause and exit_code == 0 and completed and
                 len(results) == turns and all(not r["simulated"] for r in results)
                 else "failed",
        "finished_utc":utc(),"turns_completed":len(results),
        "elapsed_seconds":round(time.monotonic() - started, 3),
        "peak_process_tree_rss_sampled_bytes":peak_rss,
        "process_rss_measured":peak_rss is not None,
        "ram_abort":low_ram_abort,
        "failure":cause or (fail.get("reason") if fail else None),
        "worker_exit_code":exit_code,
        "results":results,
        "notes":[
            "Apenas execucao local real. Nenhuma ferramenta externa foi usada.",
            "RSS inclui o processo de teste e descendentes amostrados com psutil opcional; "
            "se psutil estiver ausente, o campo fica nulo.",
            "Leituras fisicas do SSD, TTFT de audio e STT/TTS nao foram medidos.",
            "Os prompts e trechos das respostas ficam apenas neste JSON local ignorado pelo Git.",
        ],
    })
    save_report(report_path, report)
    return report

def simulate(turns: int, tokens: int, output: Path) -> dict:
    events = output.with_suffix(".events.jsonl")
    if events.exists():
        raise FileExistsError("Arquivo de eventos anterior existe; altere --output.")
    engine = SimulatedEngine()
    try:
        engine.start()
        results = run_turns(engine, turns=turns, tokens=tokens,
                            event_path=events, simulated=True)
    finally:
        engine.close()
    report = {"schema":1,"kind":"luna_stress_simulation",
              "status":"simulated","real_inference":False,
              "turns_completed":len(results),"results":results,
              "notice":"Apenas teste do orquestrador; nao executou Qwen, STT ou TTS."}
    save_report(output, report)
    return report

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    opts = parser.add_mutually_exclusive_group(required=True)
    opts.add_argument("--real",action="store_true",help="Inferencia pesada real (Windows; exige 4B instalado)")
    opts.add_argument("--simulate",action="store_true",help="Estresse do orquestrador, sem Qwen")
    opts.add_argument("--check",action="store_true",help="Conferir modelo e RAM sem iniciar Qwen")
    opts.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--turns",type=int,default=24)
    parser.add_argument("--tokens",type=int,default=96)
    parser.add_argument("--core-mode",choices=("auto","subprocess","persistent"),default="auto")
    parser.add_argument("--max-minutes",type=int,default=90)
    parser.add_argument("--per-turn-seconds",type=int,default=360)
    parser.add_argument("--output",type=Path,
                        default=ROOT / "results" / "model_comparison" / "qwen3-4b-stress.json")
    parser.add_argument("--events",type=Path,default=None,help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 1 <= args.turns <= 2000 or not 48 <= args.tokens <= 256:
        parser.error("Limites: 1-2000 turnos; 48-256 tokens.")
    if not 5 <= args.max_minutes <= 240 or not 30 <= args.per_turn_seconds <= 1200:
        parser.error("Limites: 5-240 minutos no total e 30-1200 segundos/turno.")
    try:
        if args.worker:
            if args.events is None or os.name != "nt":
                raise ValueError("Worker privado so aceita Windows e --events.")
            return worker(args.events, args.turns, args.tokens, args.core_mode)
        if args.check:
            info = require_model()
            print(json.dumps({"status":"ready_to_stress","evidence":info},ensure_ascii=False))
            return 0
        if args.real and os.name != "nt":
            raise ValueError("Teste pesado real exige Windows.")
        if args.real:
            report = supervise(report_path=args.output, turns=args.turns,
                               tokens=args.tokens, mode=args.core_mode,
                               max_minutes=args.max_minutes,
                               per_turn_seconds=args.per_turn_seconds)
        else:
            report = simulate(args.turns, args.tokens, args.output)
        print(json.dumps({
            "status":report["status"],
            "real_inference":report["real_inference"],
            "turns_completed":report["turns_completed"],
            "output":str(args.output),
            "peak_process_tree_rss_sampled_bytes":report.get("peak_process_tree_rss_sampled_bytes"),
            "failure":report.get("failure"),
        },ensure_ascii=False),flush=True)
        return 0 if report["status"] in ("passed","simulated") else 2
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("Teste nao concluido: " + str(exc),file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
