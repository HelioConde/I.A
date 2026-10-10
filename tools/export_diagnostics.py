#!/usr/bin/env python3
"""Export a bounded, sanitized diagnostic ZIP for a manual review."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.diagnostics import default_diagnostics_dir, export_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="Empacotar logs sanitizados do Brain-SSD para diagnóstico")
    parser.add_argument("--logs-dir", type=Path, default=default_diagnostics_dir())
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = args.output or default_diagnostics_dir().parent / "exports" / f"brain-ssd-diagnostics-{stamp}.zip"
    summary = export_diagnostics(args.logs_dir, dest)
    print("Pacote gerado:", dest.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Nenhum arquivo é enviado automaticamente. Inspecione o ZIP antes de compartilhá-lo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
