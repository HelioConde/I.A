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
