#!/usr/bin/env python3
"""One-command explicit setup of local Luna GameDev 9B, no chat changes."""
from __future__ import annotations
import argparse,os,shutil,sys
from pathlib import Path
from install_ornith_game_model import install as install_gguf,MODEL_FILE
from install_ornith_game_runtime import install as install_native,DEST
from luna_game_model_selector import choose_game_coder

ROOT=Path(__file__).resolve().parents[1]
MIN_DISK_FREE=7_200_000_000

def provision(root:Path=ROOT,*,check_space:bool=True)->dict:
    root=root.resolve()
    root.mkdir(parents=True,exist_ok=True)
    if check_space and not (root/"models"/MODEL_FILE).exists():
        free=shutil.disk_usage(root).free
        if free<MIN_DISK_FREE:
            raise OSError("Insufficient free disk space: require about 7.2 GB for GGUF and temporary files")
    # Install separate runtime first; Qwen default research remains unchanged.
    executable=install_native(root)
    output=install_gguf(root)
    selected,filename=choose_game_coder(root,"ornith-1.5-9b")
    return {"runtime":str(executable),"model":filename,"selector":selected,
            "install_status":output,"regular_chat_changed":False}

def main()->int:
    p=argparse.ArgumentParser(description="Luna GameDev 9B local installation for Windows 16 GB")
    p.add_argument("--confirm-download",action="store_true",
                   help="Permite ~5,78 GB do GGUF e 24 MB do runtime llama.cpp")
    a=p.parse_args()
    print("Luna GameDev: Ornith1.5 9B Q4_K_M; SHA verified model and separate Windows CPU runtime")
    print("Preserva Qwen3-4B e todas as memórias/histórico do chat.")
    if not a.confirm_download:
        print("Modo simulação. Para autorizar downloads: py tools/setup_luna_gamedev_v4.py --confirm-download")
        return 0
    if os.name!="nt" or sys.maxsize<2**32:
        print("Este setup completo é somente para Windows 64 bits.",file=sys.stderr)
        return 2
    try:
        result=provision()
        print(result)
        return 0
    except (OSError,ValueError,FileExistsError) as exc:
        print("Preparação abortada:",str(exc)[:250],file=sys.stderr)
        return 1

if __name__=="__main__":raise SystemExit(main())
