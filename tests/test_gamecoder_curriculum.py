import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"benchmarks/gamecoder_curriculum/tasks.json"

def test_original_curriculum_has_distinct_tasks():
    d=json.loads(DATA.read_text(encoding="utf-8"))
    assert d["schema_version"]==1
    assert len({t["id"] for t in d["tasks"]})==3
    assert set(t["skill"] for t in d["tasks"])=={"fsm","debug","event_bus"}

def test_cases_have_expected_outputs():
    d=json.loads(DATA.read_text(encoding="utf-8"))
    for t in d["tasks"]:
        if "cases" in t:
            assert all("expected" in c for c in t["cases"])

def test_no_external_reference_solution_leakage():
    raw=DATA.read_text(encoding="utf-8").lower()
    assert "escudeiro" not in raw
    assert "github.com" not in raw
