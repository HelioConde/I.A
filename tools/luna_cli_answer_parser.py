"""Remove the official llama.cpp *CLI wrapper*, not any model-written code.

llama-cli in interactive mode prints a launch banner, echoes/truncates the
prompt, and appends timings. Previous GameDev tests erroneously parsed those
lines as JavaScript. Keep raw stdout separately for audit.
"""
from __future__ import annotations
import re

def extract_native_answer(stdout: str) -> str:
    if not isinstance(stdout,str) or not stdout.strip():
        raise ValueError("native_empty_stdout")
    value=stdout.replace("\r\n","\n")
    if not re.search(r"(?m)^Loading model\.\.\.\s*$",value):
        # Some llama-completion builds emit raw text without a banner.
        return value.strip()
    # For long CLI prompts the echo is truncated to one line.
    marker=re.search(r"(?m)^[^\n]*\(truncated\)[^\n]*\n",value)
    if marker is None:
        marker=re.search(r"(?m)^> [^\n]*\n",value)
    if marker is None:
        raise ValueError("native_unrecognized_prompt_echo")
    after_prompt=value[marker.end():]
    timing=re.search(r"(?m)^\[ Prompt: [^\n]*\| Generation: [^\n]*\]\s*$",after_prompt)
    if timing is None:
        raise ValueError("native_unrecognized_completion_footer")
    answer=after_prompt[:timing.start()].strip()
    if not answer:
        raise ValueError("native_missing_generated_answer")
    return answer
