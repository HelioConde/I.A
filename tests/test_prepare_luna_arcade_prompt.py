import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("luna_prompt_preparer",ROOT/"tools/prepare_luna_arcade_prompt.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def test_preparation_uses_trained_router_and_real_model_without_claiming_finetune(tmp_path):
    prompt=tmp_path/"prompt.txt";report=tmp_path/"report.json"
    result=module.prepare(prompt,report)
    assert result["router_type"]=="multinomial_naive_bayes"
    assert len(result["selections"])==3
    assert all(x["skill"] for x in result["selections"])
    assert result["gamecoder_fine_tuned"] is False
    assert result["gameplay_model_run"] is False
    assert "ArrowDown" in prompt.read_text(encoding="utf-8")
    assert "Qwen3-4B" in report.read_text(encoding="utf-8")
    assert json.loads(report.read_text(encoding="utf-8"))==result

def test_preparation_m2_uses_combat_and_visual_skills(tmp_path):
    prompt=tmp_path/"m2.txt"
    report=tmp_path/"m2.json"
    evidence=module.prepare(prompt,report,stage="m2")
    task_text=" ".join(item["task"].lower() for item in evidence["selections"])
    assert evidence["stage"]=="m2"
    assert "combo" in task_text and "personagem" in task_text
    assert "KeyX" in prompt.read_text(encoding="utf-8")
    assert "Skills selecionadas pelo roteador treinado" in prompt.read_text(encoding="utf-8")
    assert evidence["gamecoder_fine_tuned"] is False

def test_unknown_stage_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="Unknown arcade stage"):
        module.prepare(tmp_path/"prompt.txt",tmp_path/"report.json",stage="invalid")
