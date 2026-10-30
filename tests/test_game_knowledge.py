"""Tests for Luna GameDev knowledge source integrity."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "validate_game_knowledge.py"
spec = importlib.util.spec_from_file_location("validate_game_knowledge", MODULE)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def test_catalog_is_valid():
    assert validator.main() == 0


def test_holdout_leakage_is_rejected():
    data = {"schema_version": 1, "policy": {"eval_isolation": "strict"}, "sources": [
        {"id": "a", "repository": "owner/repo", "license": "MIT", "split": "eval_holdout"},
        {"id": "b", "repository": "owner/repo", "license": "MIT", "split": "candidate_train"},
    ]}
    assert any("Holdout leakage" in err for err in validator.validate_sources(data))


def test_incomplete_skill_is_rejected():
    assert validator.validate_skills({"schema_version": 1, "skills": [{"id": "gdd"}]})
