#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_hud import main


if __name__ == "__main__":
    default_result = ROOT / "results/phase4d/end-to-end.json"
    arguments = sys.argv[1:]
    if arguments and not arguments[0].startswith("-"):
        result, arguments = Path(arguments[0]), arguments[1:]
    else:
        result = default_result
    raise SystemExit(main(["--result", str(result), *arguments]))
