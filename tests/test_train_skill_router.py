import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("train_skill_router",ROOT/"tools/train_skill_router.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_training_and_eval_is_deterministic():
    a,ra=mod.train_and_evaluate()
    b,rb=mod.train_and_evaluate()
    assert a==b and ra==rb
    assert ra["train_examples"]==27
    assert ra["test_examples"]==9

def test_router_rejects_unknown_labels(tmp_path):
    data=json.loads(mod.DATA.read_text(encoding="utf-8"))
    data["examples"][0]["skill"]="invalid_skill"
    p=tmp_path/"bad.json";p.write_text(json.dumps(data),encoding="utf-8")
    try:mod.train_and_evaluate(p);assert False,"expected error"
    except ValueError as error:assert "Unknown skill" in str(error)

def test_training_cannot_access_heldout_project():
    data=json.loads(mod.DATA.read_text(encoding="utf-8"))
    assert "escudeiro" not in json.dumps(data,ensure_ascii=False).casefold()
