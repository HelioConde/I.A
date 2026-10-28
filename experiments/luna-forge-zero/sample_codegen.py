"""Sample from Luna MiniCoder Zero weights; do not execute unchecked output."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import torch
from luna_codegen_model import Config,LunaMiniCoder

def sample(folder,prompt,chars=210,temperature=.65,seed=5):
    root=Path(folder)
    report=json.loads((root/'report.json').read_text())
    model=LunaMiniCoder(Config(**report['config']))
    model.load_state_dict(torch.load(root/'weights.pt',map_location='cpu',weights_only=True))
    torch.manual_seed(seed)
    return model.generate(prompt,chars=chars,temperature=temperature)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--model',default='checkpoints/luna-minicoder-zero-v0')
    ap.add_argument('--task',default='TAREFA: mover jogador velocidade 200\nLINGUAGEM: javascript\nCODIGO:\n')
    ap.add_argument('--temperature',type=float,default=.6)
    a=ap.parse_args()
    print(sample(a.model,a.task.replace('\\n','\n'),temperature=a.temperature))
