"""Prepare Luna Arcade prompt with the *trained* Luna skill router.

The learned classifier is fitted on the curated training split; this tool
does not train or change the GGUF GameCoder language model.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TRAINER=ROOT/"tools/train_skill_router.py"
spec=importlib.util.spec_from_file_location("luna_skill_trainer",TRAINER)
trainer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(trainer)
MISSION=ROOT/"benchmarks/luna_arcade_s1/mission.json"
PROMPTS={
    "m1":ROOT/"benchmarks/luna_arcade_s1/prompt_m1.txt",
    "m2":ROOT/"benchmarks/luna_arcade_s1/prompt_m2.txt",
}
TASKS_M1=(
    ("Movimentação com gravidade, pulo e estados do personagem", "fsm"),
    ("Investigue erros de colisão e passagem por plataformas", "debug"),
    ("Crie eventos para avisar a interface quando um inimigo morrer", "event_bus"),
)
TASKS_M2=(
    ("Projete estados de combo, ataque básico e especial com animações", "fsm"),
    ("Corrija ataques que acertam inimigos atrás do personagem", "debug"),
    ("Prepare descrição consistente de personagem e inimigos 2D", "asset_prompt"),
)
def prepare(output:Path,report:Path,stage:str="m1")->dict:
    if stage not in PROMPTS: raise ValueError("Unknown arcade stage")
    model, evaluation=trainer.train_and_evaluate()
    mission=json.loads(MISSION.read_text(encoding="utf-8"))
    original=PROMPTS[stage].read_text(encoding="utf-8")
    selections=[{"task":task,"skill":trainer.predict(model,task),"expected_hint":expected}
                for task,expected in (TASKS_M1 if stage=="m1" else TASKS_M2)]
    skills={s["id"]:s for s in json.loads((ROOT/"knowledge/game_dev/skills.json").read_text(encoding="utf-8"))["skills"]}
    descriptions=[]
    for selection in selections:
        selected=skills[selection["skill"]]
        descriptions.append(f'- {selection["task"]}: skill={selected["id"]}; verificação={", ".join(selected["checks"])}')
    guidance="\n\nSkills selecionadas pelo roteador treinado (orientações, não código pronto):\n"+"\n".join(descriptions)
    output.parent.mkdir(parents=True,exist_ok=True)
    report.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(original+guidance+"\n",encoding="utf-8")
    evidence={"schema_version":1,"mission":mission["name"],"stage":stage,"router_type":model["model_type"],
              "router_dataset_sha256":model["dataset_sha256"],
              "router_test_accuracy":evaluation["accuracy"],"selections":selections,
              "gamecoder_model":"Qwen3-4B-Q4_K_M.gguf",
              "gamecoder_fine_tuned":False,"gameplay_model_run":False}
    report.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return evidence

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--stage",choices=tuple(PROMPTS),default="m1")
    a=p.parse_args()
    print(json.dumps(prepare(a.output,a.report,stage=a.stage),ensure_ascii=False))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
