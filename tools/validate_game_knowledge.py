"""Read-only validator for Luna GameDev source and skill manifests.

Run: python tools/validate_game_knowledge.py
No downloads, imports from external repositories, model execution, or side effects.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "knowledge" / "game_dev"
ALLOWED_SPLITS = {"reference", "candidate_train", "eval_holdout"}
ALLOWED_LICENSES = {"MIT", "Apache-2.0"}


def validate_sources(data: dict) -> list[str]:
    errors: list[str] = []
    sources = data.get("sources", [])
    if data.get("schema_version") != 1 or not isinstance(sources, list):
        return ["Invalid source schema"]
    seen: set[str] = set()
    repo_splits: dict[str, set[str]] = {}
    for source in sources:
        identifier = source.get("id", "")
        repo = source.get("repository", "")
        split = source.get("split")
        if not identifier or identifier in seen:
            errors.append(f"Missing or duplicate source id: {identifier}")
        seen.add(identifier)
        if not isinstance(repo, str) or repo.count("/") != 1:
            errors.append(f"Invalid repository: {repo}")
        if source.get("license") not in ALLOWED_LICENSES:
            errors.append(f"Unreviewed license: {identifier}")
        if split not in ALLOWED_SPLITS:
            errors.append(f"Invalid split: {identifier}")
        repo_splits.setdefault(repo, set()).add(split)
    for repo, splits in repo_splits.items():
        if "eval_holdout" in splits and len(splits) > 1:
            errors.append(f"Holdout leakage: {repo}")
    if not data.get("policy", {}).get("eval_isolation"):
        errors.append("Missing holdout isolation policy")
    return errors


def validate_skills(data: dict) -> list[str]:
    skills = data.get("skills", [])
    if data.get("schema_version") != 1 or not isinstance(skills, list):
        return ["Invalid skill schema"]
    errors: list[str] = []
    names: set[str] = set()
    for skill in skills:
        name = skill.get("id")
        if not name or name in names:
            errors.append(f"Duplicate or missing skill: {name}")
        names.add(name)
        if not all(skill.get(field) for field in ("input", "output", "checks")):
            errors.append(f"Incomplete skill contract: {name}")
    return errors


def main() -> int:
    sources = json.loads((BASE / "sources.json").read_text(encoding="utf-8"))
    skills = json.loads((BASE / "skills.json").read_text(encoding="utf-8"))
    errors = validate_sources(sources) + validate_skills(skills)
    for error in errors:
        print("FAIL:", error)
    if errors:
        return 1
    print(f"PASS: {len(sources['sources'])} sources, {len(skills['skills'])} skill contracts, holdout isolated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
