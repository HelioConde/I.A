"""Check generated Lua syntax via luac -p when installed.

Never uses the commercial game folder; never invokes Lua interpreter or runs
the generated code. This is parser/bytecode validation only. An absent luac
is explicitly UNAVAILABLE rather than a successful parse.
"""
from __future__ import annotations
from pathlib import Path
import shutil
import subprocess
import tempfile

def syntax_check_lua(generated: str, *, compiler: str | None = None) -> str:
    if not isinstance(generated,str):
        raise TypeError("Generated Lua source must be a string")
    if len(generated)>12000:
        raise ValueError("Generated code exceeded syntax validation budget")
    exe = compiler if compiler is not None else shutil.which("luac")
    if not exe:
        return "UNAVAILABLE_NO_LUAC"
    if not generated.strip():
        return "FAIL_EMPTY"
    try:
        with tempfile.TemporaryDirectory(prefix="luna_lua_syntax_") as folder:
            candidate=Path(folder)/"generated.lua"
            candidate.write_text(generated,encoding="utf-8")
            process=subprocess.run(
                [exe,"-p",str(candidate)],capture_output=True,
                text=True,check=False,timeout=8,
            )
            # Never publish parser output: it includes local temp paths and
            # occasionally snippets of generated content.
            return "PASS" if process.returncode==0 else "FAIL"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except OSError:
        return "ERROR_COMPILER"
