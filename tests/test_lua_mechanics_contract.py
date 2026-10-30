import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_unique_mechanics_and_one_way_requirements():
    d=json.loads((ROOT/'benchmarks/luna_arcade_s1/lua_mechanics_contract.json').read_text(encoding='utf-8'))
    assert d['schema_version']==1
    assert len(d['mechanics'])==5
    assert len({m['id'] for m in d['mechanics']})==5
    assert any('ArrowDown' in m['inputs'] for m in d['mechanics'])
    assert all(m.get('setup') and m.get('expected') for m in d['mechanics'])
