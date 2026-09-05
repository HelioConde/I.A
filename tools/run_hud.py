#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from brain_ssd.hud import HudRuntime, create_server
from brain_ssd.observability.demo import build_demo_events
from brain_ssd.observability.replay import phase4d_replay_events, phase_catalog
from brain_ssd.observability.snapshots import write_snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Brain-SSD read-only Visual HUD")
    parser.add_argument("--host", default="0.0.0.0", help="bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="stream an explicitly synthetic demo")
    mode.add_argument("--result", type=Path, help="replay a canonical Phase 4D end-to-end JSON")
    parser.add_argument("--query-id", help="Phase 4D query_id to replay")
    parser.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier")
    parser.add_argument("--hide-query", action="store_true")
    parser.add_argument("--hide-records", action="store_true")
    parser.add_argument("--hide-answer", action="store_true")
    parser.add_argument("--snapshot-output", type=Path, help="write final projected state as JSON")
    return parser


def _stream(runtime: HudRuntime, events, speed: float, snapshot_output: Path | None, privacy: dict[str, bool]) -> None:
    previous = events[0].timestamp if events else time.time()
    for event in events:
        delay = max(0.0, event.timestamp - previous) / max(speed, 0.01)
        time.sleep(min(delay, 2.0))
        runtime.emit(event)
        previous = event.timestamp
    if snapshot_output:
        write_snapshot(snapshot_output, runtime.state.snapshot(), **privacy)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    runtime = HudRuntime()
    phases = phase_catalog(ROOT)
    events = []
    if args.demo:
        events = build_demo_events()
        runtime.state.reset(data_source="DEMO DATA · valores sintéticos", demo_data=True, phases=phases)
    elif args.result:
        result_path = args.result if args.result.is_absolute() else ROOT / args.result
        events, phases, data_source = phase4d_replay_events(result_path, ROOT, args.query_id)
        runtime.state.reset(data_source=data_source, demo_data=False, phases=phases)
    else:
        runtime.state.reset(data_source="LIVE EVENT BUS · aguardando eventos", demo_data=False, phases=phases)

    privacy = {
        "hide_query": args.hide_query,
        "hide_records": args.hide_records,
        "hide_answer": args.hide_answer,
    }
    server = create_server(
        runtime,
        ROOT / "hud",
        args.host,
        args.port,
        **privacy,
    )
    actual_host, actual_port = server.server_address
    display_host = "127.0.0.1" if actual_host in {"0.0.0.0", "::"} else actual_host
    print("BRAIN-SSD VISUAL HUD", flush=True)
    print(f"URL: http://{display_host}:{actual_port}", flush=True)
    print(f"SOURCE: {runtime.state.snapshot()['data_source']}", flush=True)
    print("READ-ONLY: o HUD não altera o pipeline cognitivo.", flush=True)
    print("Pressione Ctrl+C para encerrar.", flush=True)

    if events:
        threading.Thread(
            target=_stream,
            args=(runtime, events, args.speed, args.snapshot_output, privacy),
            name="hud-replay",
            daemon=True,
        ).start()
    elif args.snapshot_output:
        write_snapshot(args.snapshot_output, runtime.state.snapshot(), **privacy)

    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
