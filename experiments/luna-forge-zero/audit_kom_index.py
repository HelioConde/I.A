"""Metadata-only KOM index audit. Never extracts, decrypts, or executes entries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kom_audit import audit_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Explicit local KOM file or directory")
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional new JSON file; existing files are never overwritten",
    )
    args = parser.parse_args()
    report = audit_path(args.path)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out is not None:
        with args.json_out.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
    print(encoded, end="")
    return 0 if not report["errors"] and not report["partial"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
