"""Train an isolated, original-data Luna MiniCoder V3 candidate from scratch."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import time

import torch

from luna_minicoder_v3 import (
    LunaMiniCoderV3,
    V3Config,
    collate_completions,
    make_prompt,
)


HERE = Path(__file__).resolve().parent
DEFAULT_CURRICULUM = HERE / "minicoder_v3_curriculum.json"


def load_curriculum(path: Path = DEFAULT_CURRICULUM) -> tuple[dict, dict[str, list[dict]]]:
    path = Path(path)
    if path.is_symlink() or path.resolve() != DEFAULT_CURRICULUM.resolve():
        raise ValueError("V3 accepts only the checked-in original curriculum")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "luna-minicoder-v3-curriculum-v1":
        raise ValueError("Unsupported V3 curriculum schema")
    splits = document.get("splits", {})
    tasks = document.get("tasks", [])
    groups = {name: [] for name in ("train", "validation", "test")}
    ids: set[str] = set()
    for task in tasks:
        split = task.get("split")
        if split not in groups or task.get("id") in ids:
            raise ValueError("Curriculum has an invalid split or duplicate task id")
        ids.add(task["id"])
        if task.get("project") != splits[split].get("project"):
            raise ValueError(f"Task {task['id']} project does not match split manifest")
        if task.get("family") not in splits[split].get("families", []):
            raise ValueError(f"Task {task['id']} family does not match split manifest")
        if not task.get("objective") or not task.get("function_name") or not task.get("parameters"):
            raise ValueError("Every task needs structured task, function, and parameter metadata")
        if split == "test":
            if task.get("solution") is not None:
                raise ValueError("Reserved test tasks must not contain reference solutions")
            if not task.get("cases"):
                raise ValueError("Reserved test tasks need functional cases")
        else:
            solution = task.get("solution")
            if not isinstance(solution, str) or not solution.startswith(
                f"function {task['function_name']}("
            ):
                raise ValueError(f"Task {task['id']} needs its original complete function solution")
            prompt = make_prompt(task)
            if len(prompt.encode("ascii")) + len(solution.encode("ascii")) + 1 > V3Config().block:
                raise ValueError(f"Task {task['id']} exceeds the V3 context budget")
        groups[split].append(task)
    if not groups["train"] or not groups["validation"] or not groups["test"]:
        raise ValueError("V3 requires non-empty train, validation, and test splits")

    split_names = tuple(groups)
    for left_index, left in enumerate(split_names):
        for right in split_names[left_index + 1:]:
            left_projects = {task["project"] for task in groups[left]}
            right_projects = {task["project"] for task in groups[right]}
            left_families = {task["family"] for task in groups[left]}
            right_families = {task["family"] for task in groups[right]}
            if left_projects & right_projects or left_families & right_families:
                raise ValueError(f"{left}/{right} project or mechanic-family leakage")
    train_ids = {task["id"] for task in groups["train"]}
    seen = document.get("seen_diagnostic_ids", [])
    if not seen or not set(seen) <= train_ids:
        raise ValueError("Seen diagnostic references must be a non-empty subset of train ids")
    document["seen_diagnostic_ids"] = seen
    return document, groups


def _mean_loss(model: LunaMiniCoderV3, examples: list[dict]) -> float:
    model.eval()
    inputs, labels = collate_completions(examples, model.cfg)
    with torch.inference_mode():
        _, loss = model(inputs, labels)
    return float(loss.item())


def train(
    out: Path,
    *,
    curriculum: Path = DEFAULT_CURRICULUM,
    steps: int = 400,
    batch_size: int = 4,
    threads: int = 2,
    seed: int = 20261029,
) -> dict:
    if not 1 <= steps <= 5000 or not 1 <= batch_size <= 16 or not 1 <= threads <= 8:
        raise ValueError("CPU training limits: steps 1..5000, batch 1..16, threads 1..8")
    document, groups = load_curriculum(curriculum)
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite an existing V3 experiment: {out}")

    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    chooser = random.Random(seed)
    config = V3Config()
    model = LunaMiniCoderV3(config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)
    train_examples = groups["train"]
    seen_examples = [task for task in train_examples if task["id"] in document["seen_diagnostic_ids"]]
    train_before = _mean_loss(model, train_examples)
    seen_before = _mean_loss(model, seen_examples)
    validation_before = _mean_loss(model, groups["validation"])
    history = []
    best_validation = float("inf")
    best_state = None
    best_step = 0
    final_step_train_loss = None
    started = time.perf_counter()
    for step in range(1, steps + 1):
        model.train()
        batch = [chooser.choice(train_examples) for _ in range(batch_size)]
        inputs, labels = collate_completions(batch, config)
        _, loss = model(inputs, labels)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step == 1 or step % 50 == 0 or step == steps:
            train_score = _mean_loss(model, train_examples)
            validation_score = _mean_loss(model, groups["validation"])
            record = {
                "step": step,
                "batch_completion_loss": round(float(loss.detach().item()), 6),
                "train_completion_loss": round(train_score, 6),
                "validation_completion_loss": round(validation_score, 6),
            }
            history.append(record)
            print(json.dumps(record), flush=True)
            final_step_train_loss = train_score
            if validation_score < best_validation:
                best_validation = validation_score
                best_step = step
                best_state = copy.deepcopy(model.state_dict())

    if best_state is None:
        raise RuntimeError("Training did not produce a validation checkpoint")
    model.load_state_dict(best_state)
    train_after = _mean_loss(model, train_examples)
    seen_after = _mean_loss(model, seen_examples)
    validation_after = _mean_loss(model, groups["validation"])
    out.mkdir(parents=True)
    weights = out / "weights.pt"
    torch.save(model.state_dict(), weights)
    weights_hash = hashlib.sha256(weights.read_bytes()).hexdigest()
    curriculum_bytes = Path(curriculum).read_bytes()
    parameters = sum(parameter.numel() for parameter in model.parameters())
    report = {
        "schema": "luna-minicoder-v3-experiment-v1",
        "model_type": "luna_minicoder_v3_sft",
        "status": "candidate_not_promoted",
        "initialization": "random; no V0/V2 weights loaded",
        "data_provenance": document["provenance"],
        "curriculum_sha256": hashlib.sha256(curriculum_bytes).hexdigest(),
        "weights_sha256": weights_hash,
        "config": model.config_dict(),
        "parameters": parameters,
        "estimated_parameter_bytes_fp32": parameters * 4,
        "estimated_attention_scores_bytes_fp32": (
            batch_size * config.heads * config.block * config.block * 4
        ),
        "cpu_memory_budget_note": (
            "The 512-position, width-32, one-layer model is intended for local CPU; "
            "peak optimizer/activation memory depends on batch size. Default batch=4."
        ),
        "steps": steps,
        "selected_checkpoint_step": best_step,
        "last_logged_train_completion_loss": (
            round(final_step_train_loss, 6) if final_step_train_loss is not None else None
        ),
        "best_validation_completion_loss": round(best_validation, 6),
        "batch_size": batch_size,
        "threads": threads,
        "seed": seed,
        "examples_by_split": {split: len(rows) for split, rows in groups.items()},
        "training_projects": sorted({row["project"] for row in groups["train"]}),
        "validation_projects": sorted({row["project"] for row in groups["validation"]}),
        "test_projects": sorted({row["project"] for row in groups["test"]}),
        "train_families": sorted({row["family"] for row in groups["train"]}),
        "validation_families": sorted({row["family"] for row in groups["validation"]}),
        "test_families": sorted({row["family"] for row in groups["test"]}),
        "test_reference_solutions_in_training": 0,
        "seen_diagnostic_ids": document["seen_diagnostic_ids"],
        "train_completion_loss_before": round(train_before, 6),
        "train_completion_loss_after": round(train_after, 6),
        "seen_completion_loss_before": round(seen_before, 6),
        "seen_completion_loss_after": round(seen_after, 6),
        "validation_completion_loss_before": round(validation_before, 6),
        "validation_completion_loss_after": round(validation_after, 6),
        "history": history,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "test_metrics": "pending gameplay_contracts.py evaluation",
        "promotion_allowed": False,
        "interpretation": "Completion loss is not evidence of syntax or gameplay capability.",
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train isolated Luna MiniCoder V3 from scratch")
    parser.add_argument("--out", type=Path, default=HERE / "checkpoints" / "luna-minicoder-v3-candidate")
    parser.add_argument("--curriculum", type=Path, default=DEFAULT_CURRICULUM)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()
    report = train(
        args.out,
        curriculum=args.curriculum,
        steps=args.steps,
        batch_size=args.batch,
        threads=args.threads,
        seed=args.seed,
    )
    print(json.dumps({key: value for key, value in report.items() if key != "history"},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
