"""Select the strongest *installed and verified* local Luna GameDev GGUF.

This affects only coding experiments, not regular Luna chat, research core
or the existing Qwen-authored game and its audited provenance.
"""
from __future__ import annotations
from pathlib import Path

from install_game_coder_model import MODEL_FILENAME as QWEN_FILE,MODEL_SHA256 as QWEN_SHA
from install_ornith_game_model import MODEL_FILE as ORNITH_FILE,MODEL_SHA256 as ORNITH_SHA
from install_windows_chat import verified_file

PREFERRED=("ornith-1.5-9b",ORNITH_FILE,ORNITH_SHA)
FALLBACK=("qwen3-4b",QWEN_FILE,QWEN_SHA)

def choose_game_coder(root:Path,requested:str="auto")->tuple[str,str]:
    """Returns (model label, GGUF filename); no download or automatic promotion."""
    candidates=(PREFERRED,FALLBACK)
    if requested!="auto":
        names={name:(name,filename,digest) for name,filename,digest in candidates}
        by_file={filename:(name,filename,digest) for name,filename,digest in candidates}
        selected=names.get(requested) or by_file.get(requested)
        if selected is None:
            raise ValueError("Unrecognized GameDev GGUF selector")
        candidates=(selected,)
    for name,filename,digest in candidates:
        target=root/"models"/filename
        if not target.exists():
            continue
        if not verified_file(target,sha256=digest):
            raise ValueError("Invalid model SHA256: "+filename)
        return name,filename
    raise FileNotFoundError("Nenhum modelo GameDev íntegro. Execute o instalador GGUF desejado.")
