"""Validate Luna Arcade M2 evaluation requirements, not gameplay success."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"benchmarks/luna_arcade_s1/m2_combat_visual.json"

def test_combat_visual_contract():
    data=json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    expected={"three_hit_combo","facing_hitbox","hit_reaction","original_visuals","regression"}
    assert {c["id"] for c in data["acceptance"]} == expected
    assert all(c.get("description") and c.get("evidence") for c in data["acceptance"])
    assert data["controls"]["KeyZ"]=="basic combo"
    assert data["controls"]["KeyX"]=="special skill"

def test_authorship_is_truthful():
    data=json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert "only output from verified Qwen GGUF runtime is Luna code" in data["authorship"]
    assert any("No fabricated" in item for item in data["constraints"])
