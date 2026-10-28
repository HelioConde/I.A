"""Procedural evaluation of the new game planner; no automatic weight mutation."""
import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from luna_model import FEATURES, GENRES, load_model, predict
from train import sample

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--model',default='checkpoints/luna-forge-zero-v0')
    ap.add_argument('--rounds',type=int,default=200)
    ap.add_argument('--seed',type=int,default=98531)
    ap.add_argument('--out',default='reports/teacher_round.json')
    args=ap.parse_args()
    if args.rounds<1:ap.error('--rounds must be positive')
    model,vocab,_=load_model(args.model)
    rng=random.Random(args.seed)
    counts=Counter()
    failures=[]
    for _ in range(args.rounds):
        question,genre,expected=sample(rng)
        response=predict(question,model,vocab)
        target={f:bool(v) for f,v in zip(FEATURES,expected)}
        wrong=[f for f in FEATURES if response['features'][f]!=target[f]]
        if response['genre']!=GENRES[genre]:wrong.append('genre')
        if wrong:
            counts.update(wrong)
            failures.append({'task':question,'expected':{'genre':GENRES[genre],'features':target},'predicted':response,'error_types':wrong})
    report={'date_utc':datetime.now(timezone.utc).isoformat(),'origin':'procedurally generated challenges, separate seed','rounds':args.rounds,'exact_accuracy':(args.rounds-len(failures))/args.rounds,'errors_by_type':dict(counts),'examples':failures[:50],'note':'No model teacher yet; human review required before retraining'}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='examples'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
