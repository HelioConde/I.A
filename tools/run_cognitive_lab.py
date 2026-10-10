#!/usr/bin/env python3
"""Deterministic offline neuroscience-inspired *engineering* demo.

Does not download models, use the internet, read a user's conversations, or
perform autonomous computer actions. Operates in TemporaryDirectory only.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.cognitive_lab import (
    GridWorld, prediction_error, propose_associations,
    replay_preview, select_attention, working_state, TabularActionLearner,
)
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.plasticity import PlasticityLedger, PredictionJournal
from brain_ssd.chat.consolidation import ConsolidationQueue


def evaluate() -> dict:
    with tempfile.TemporaryDirectory(prefix="brain-ssd-lab-") as temp:
        memory = EpisodicMemory(Path(temp) / "examples.sqlite3")
        first = memory.add("Reunião Python terça biblioteca norte")
        second = memory.add("Reunião Python quinta biblioteca sul")
        third = memory.add("Teste da nave rover azul usa lidar")
        notes = memory.list()
        cue = "Reunião Python biblioteca"
        candidates = memory.recall(cue)
        attention = select_attention(cue, [
            {"id": row["id"], "text": row["content"]}
            for row in candidates
        ], max_records=2, max_bytes=500)
        state = working_state([
            {"role": "user", "content": "Estamos planejando uma reunião Python"},
            {"role": "assistant", "content": "Vamos pensar no local da reunião"},
            {"role": "user", "content": cue},
        ])
        replay = replay_preview(notes)
        ledger = PlasticityLedger(Path(temp) / "feedback.sqlite3", memory)
        events = [ledger.add_feedback(first["id"], 1) for _ in range(3)]
        before_revert = ledger.shadow_bias(first["id"])
        ledger.revoke(events[0])
        after_revert = ledger.shadow_bias(first["id"])
        prediction_journal=PredictionJournal(Path(temp) / "predictions.sqlite3")
        prediction_before=prediction_journal.predict("grid_goal_success")
        prediction_observation=prediction_journal.observe("grid_goal_success",True)
        prediction_after=prediction_journal.predict("grid_goal_success")
        prediction_journal.revoke(prediction_observation["id"])
        prediction_reverted=prediction_journal.predict("grid_goal_success")
        queue=ConsolidationQueue(Path(temp) / "reviews.sqlite3",memory)
        review_draft=queue.create_draft([first["id"], second["id"]])
        review=queue.review(review_draft["id"],"approve","Duas reuniões diferentes sobre Python")
        queue.revoke(review_draft["id"])
        expectation = prediction_error(0.7, True)
        agent = TabularActionLearner(seed=17)
        policy_before = agent.evaluate()
        learned = agent.train(episodes=400,epsilon=.3)
        policy_after = agent.evaluate()
        world = GridWorld()
        trace = [world.step(a) for a in ["right"] * 4 + ["down"] * 4]
        return {
            "classification": "OFFLINE_SYNTHETIC_SHADOW_ONLY",
            "attention": {"selected": len(attention.selected_ids), "inhibited": len(attention.inhibited_ids),
                          "activation_bytes": attention.activation_bytes},
            "working_memory": state.to_dict(),
            "episodic": {"total": len(notes), "retrieved": len(candidates),
                         "individual_ids_retained": first["id"] != second["id"]},
            "associations": {"shadow_proposals": len(propose_associations(notes))},
            "replay": {"mode": replay.mode, "candidates": len(replay.candidate_ids),
                       "writes_to_model": replay.writes_to_model},
            "plasticity": {"status": "SHADOW_ONLY",
                           "bias_with_3_explicit_signals": before_revert["bias"],
                           "bias_after_revoke": after_revert["bias"],
                           "weights_updated": False},
            "consolidation": {"review_was_explicit": review["state"] == "REVIEWED", "reversible": queue.list()[0]["state"] == "REVOKED", "promoted_to_qwen": False},
            "online_prediction_learning": {"before":prediction_before["probability"], "after_verified_outcome":prediction_after["probability"], "after_revoke":prediction_reverted["probability"], "qwen_weights_changed":False},
            "prediction": {"expected": expectation.probability,
                           "actual": expectation.observed, "brier": expectation.brier},
            "learning_cycle": {"greedy_before": policy_before, "training": learned, "greedy_after": policy_after, "only_sandbox_weights_modified": True},
            "perception_action": {"steps": len(trace), "goal_reached": world.finished,
                                  "final_position": list(world.position),
                                  "outside_machine_actions": False},
            "limitations": [
                "No Qwen inference, no user data, no unsupervised factual learning",
                "No automatic memory consolidation, no motor actuators",
                "Not a biological brain or human consciousness emulator",
            ],
        }


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not (report["perception_action"]["goal_reached"]
            and report["episodic"]["individual_ids_retained"]
            and report["plasticity"]["bias_after_revoke"] == 0
            and not report["replay"]["writes_to_model"]
            and report["learning_cycle"]["greedy_after"]["goal_reached"]
            and report["online_prediction_learning"]["after_revoke"] == 0.5
            and report["consolidation"]["reversible"]):
        raise SystemExit(1)
