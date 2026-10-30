import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_mission_contract():
    data=json.loads((ROOT/"benchmarks/luna_arcade_s1/mission.json").read_text(encoding="utf-8"))
    assert len(data["milestones"])==3
    assert "ArrowDown" in data["controls"]
    assert "three original arenas" in data["milestones"][2]["acceptance"]
    assert sum(data["evaluation"].values())==100
    assert data["status"]=="spec_only_not_completed"
def test_prompt_for_model_requires_platform_drop():
    p=(ROOT/"benchmarks/luna_arcade_s1/prompt_m1.txt").read_text(encoding="utf-8")
    assert "ArrowDown" in p and "plataforma" in p
    assert "SOMENTE JS" in p
