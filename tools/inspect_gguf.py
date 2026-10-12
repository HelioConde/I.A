#!/usr/bin/env python3
"""Print safe GGUF directory metadata; never loads or executes a model."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.gguf_inspector import GGUFError, GGUFInspector

parser = argparse.ArgumentParser(description="Read-only GGUF tensor inspector.")
parser.add_argument("source", type=Path)
parser.add_argument("--tensor", help="Inspect one tensor by exact name.")
parser.add_argument("--window-bytes", type=int, default=0,
                    help="Optionally verify a bounded leading tensor window.")
args = parser.parse_args()
try:
    view = GGUFInspector(args.source)
    tensors = [view.tensor(args.tensor)] if args.tensor else list(view.tensors)
    report = {"schema": 1, "type": "gguf_directory_read_only", "version": view.version,
              "alignment": view.alignment, "tensor_count": len(view.tensors),
              "tensors": [{"name": t.name, "shape": t.shape, "type": t.type_name,
                           "offset": t.offset, "size_bytes": t.size_bytes} for t in tensors]}
    if args.window_bytes:
        if not args.tensor or args.window_bytes < 0:
            raise ValueError("--window-bytes requires --tensor and a non-negative value.")
        report["window_verified_bytes"] = len(view.read_tensor_window(args.tensor, length=args.window_bytes))
    print(json.dumps(report, ensure_ascii=False, indent=2))
except (GGUFError, OSError, ValueError, KeyError) as exc:
    parser.exit(2, "GGUF inspection error: " + str(exc) + "\n")
