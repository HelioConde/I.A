#!/usr/bin/env python3
"""Measure OS-residency of one GGUF tensor window; never runs inference."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.gguf_inspector import GGUFInspector
from brain_ssd.native_weight_windows import NativeTensorWindow

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("--tensor", required=True)
parser.add_argument("--offset", type=int, default=0)
parser.add_argument("--length", type=int, default=4 * 1024 * 1024)
args = parser.parse_args()
if os.name != "nt":
    parser.exit(2, "Windows-native probe required.\n")
try:
    view = GGUFInspector(args.source)
    with NativeTensorWindow(view, args.tensor, offset=args.offset, length=args.length) as window:
        stats = window.touch()
    print(json.dumps({"schema": 1, "type": "native_tensor_window_residency",
                      "status": "measured", **stats.__dict__,
                      "notice": "Native mapped tensor window only; not llama.cpp inference or total Qwen RAM."}, indent=2))
except (OSError, ValueError, KeyError, RuntimeError) as exc:
    parser.exit(2, "Native window probe error: " + str(exc) + "\n")
