"""Regression checks for held-out benchmark isolation and catalog search."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brain_ssd.game_knowledge import format_for_core, load_catalog, search


def test_catalog_loads():
    sources, skills = load_catalog()
    assert len(sources) == 10
    assert len(skills) == 9


def test_matching_skill():
    matches = search("debug stack trace")
    assert any(item["id"] == "debug" and item["kind"] == "skill" for item in matches)


def test_heldout_never_retrieved_even_by_exact_name():
    assert not any(item.get("id") == "escudeiro" for item in search("Escudeiro"))
    for query in ("gdscript platformer", "eval_holdout", "MIT", "game"):
        assert all(item.get("id") != "escudeiro" for item in search(query, limit=30))


def test_empty_and_invalid_limits():
    assert search("  ") == []
    try:
        search("godot", limit=0)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_core_payload_has_provenance():
    payload = format_for_core("godot")
    assert payload["schema_version"] == 1
    assert "no third-party" in payload["notice"].lower()
    assert all(item["kind"] in ("source", "skill") for item in payload["results"])
