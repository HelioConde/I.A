"""Train a tiny character-level GPT from ZERO on synthetic JS/Godot snippets."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from dataclasses import asdict
from pathlib import Path
import torch
from luna_codegen_model import Config,LunaMiniCoder

def one(rng):
    speed=rng.choice((140,160,180,200,220,240,260,280,300))
    gravity=rng.choice((900,1100,1300,1500,1700,1900))
    life=rng.choice((2,3,4,5,6))
    kind=rng.randrange(8)
    if kind==0:return (f'TAREFA: mover jogador velocidade {speed}\nLINGUAGEM: javascript\nCODIGO:\n'
                 f'function move(player, axis, dt) {{\n  player.x += axis * {speed} * dt;\n}}\nFIM\n')
    if kind==1:return (f'TAREFA: aplicar gravidade {gravity}\nLINGUAGEM: javascript\nCODIGO:\n'
                 f'function gravity(player, dt) {{\n  player.vy += {gravity} * dt;\n  player.y += player.vy * dt;\n}}\nFIM\n')
    if kind==2:return (f'TAREFA: limitar posicao x {speed}\nLINGUAGEM: javascript\nCODIGO:\n'
                 f'function clampX(player) {{\n  player.x = Math.max(0, Math.min({speed}, player.x));\n}}\nFIM\n')
    if kind==3:return (f'TAREFA: coletar moedas\nLINGUAGEM: javascript\nCODIGO:\n'
                 'function collect(player, coin) {\n  if (Math.abs(player.x - coin.x) < 20) {\n    coin.taken = true;\n  }\n}\nFIM\n')
    if kind==4:return (f'TAREFA: dano de inimigo {life}\nLINGUAGEM: javascript\nCODIGO:\n'
                 f'function hit(player) {{\n  player.hp = Math.max(0, player.hp - {life});\n}}\nFIM\n')
    if kind==5:return (f'TAREFA: mover personagem velocidade {speed}\nLINGUAGEM: gdscript\nCODIGO:\n'
                 f'extends CharacterBody2D\nconst SPEED = {speed}.0\nfunc _physics_process(delta):\n    velocity.x = Input.get_axis("ui_left", "ui_right") * SPEED\n    move_and_slide()\nFIM\n')
    if kind==6:return (f'TAREFA: pular personagem impulso {speed}\nLINGUAGEM: gdscript\nCODIGO:\n'
                 f'extends CharacterBody2D\nconst JUMP = -{speed}.0\nfunc _physics_process(delta):\n    if is_on_floor() and Input.is_action_just_pressed("ui_accept"):\n        velocity.y = JUMP\n    move_and_slide()\nFIM\n')
    return (f'TAREFA: barra de vida inicial {life}\nLINGUAGEM: gdscript\nCODIGO:\n'
            f'extends Node2D\nvar life = {life}\nfunc damage(amount):\n    life = max(0, life - amount)\nFIM\n')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default='checkpoints/luna-minicoder-zero-v0')
    ap.add_argument('--steps',type=int,default=350)
    ap.add_argument('--batch',type=int,default=12)
    ap.add_argument('--seed',type=int,default=312)
    ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--lr',type=float,default=.001)
    args=ap.parse_args()
    torch.manual_seed(args.seed);torch.set_num_threads(args.threads)
    rng=random.Random(args.seed)
    train=''.join(one(rng) for _ in range(5500)).encode('ascii')
    val_rng=random.Random(args.seed+999)
    val=''.join(one(val_rng) for _ in range(500)).encode('ascii')
    cfg=Config()
    model=LunaMiniCoder(cfg)
    train=torch.tensor(list(train),dtype=torch.long)
    val=torch.tensor(list(val),dtype=torch.long)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    if args.resume and (out/'weights.pt').exists():
        model.load_state_dict(torch.load(out/'weights.pt',map_location='cpu',weights_only=True))
        print('resumed from saved weights', flush=True)
    opt=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=.02)
    history=[]
    def batch(tokens):
        x=torch.randint(0,len(tokens)-cfg.block-1,(args.batch,))
        idx=x[:,None]+torch.arange(cfg.block)
        return tokens[idx],tokens[idx+1]
    for step in range(1,args.steps+1):
        model.train();x,y=batch(train);_,loss=model(x,y)
        opt.zero_grad(set_to_none=True);loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        opt.step()
        if step==1 or step%100==0 or step==args.steps:
            model.eval()
            with torch.no_grad():
                x,y=batch(val);_,vloss=model(x,y)
            history.append({'step':step,'train_loss':round(float(loss.detach()),4),'validation_loss':round(float(vloss.detach()),4)})
            print(f'step {step:04d} train_loss={loss.item():.3f} val_loss={vloss.item():.3f}',flush=True)
            torch.save(model.state_dict(),out/'weights.pt')
    torch.save(model.state_dict(),out/'weights.pt')
    report={'origin':'random initial weights; all code examples synthetic/in-house','parameter_count':sum(p.numel() for p in model.parameters()),'config':asdict(cfg),'steps':args.steps,'train_chars':len(train),'val_chars':len(val),'history':history,'limitations':'Small autoregressive code-completion experiment. No guarantee of syntax, functionality or game creation. Training/test tasks share template families.'}
    report['sha256']=hashlib.sha256((out/'weights.pt').read_bytes()).hexdigest()
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
