"""Unit tests for non-executing Luna Core review of movement mechanics."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
spec=importlib.util.spec_from_file_location("luna_core_qa",LAB/"luna_core_qa.py")
qa=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)

class CoreMovementReviewTests(unittest.TestCase):
    def test_bad_but_syntactically_valid_move_is_flagged(self):
        # Invented fixture with the same bugs observed in a LOCAL model response,
        # not copied proprietary code or game assets.
        source=(
          "function moveHorizontal(player, dt, accel, friction, maxSpeed) {\n"
          "  player.velocityX *= friction;\n"
          "  player.velocityX += accel * dt;\n"
          "  player.velocityX = Math.min(player.velocityX, maxSpeed);\n"
          "  player.positionX += player.velocityX * dt;\n"
          "}\n"
        )
        result=qa.review("Movimento horizontal com aceleração, atrito e limite de velocidade",source)
        self.assertEqual(result["task_type"],"horizontal_movement")
        indicators=result["rubric"]["indicators"]
        self.assertFalse(indicators["player_direction_input"])
        self.assertFalse(indicators["symmetric_max_speed"])
        self.assertFalse(indicators["frame_rate_independent_friction"])
        self.assertFalse(indicators["neutral_input_handling"])
        self.assertTrue(indicators["delta_time_used_in_position"])
        self.assertEqual(result["rubric"]["indicators_detected"],1)
        self.assertFalse(result["rubric"]["behavior_verified"])
        self.assertFalse(result["rubric"]["quality_approved"])

    def test_good_reference_heuristics_not_functional_proof(self):
        source=(
          "function moveHorizontal(player, axis, dt, maxSpeed, friction) {\n"
          "  const clamped = Math.max(-maxSpeed, Math.min(maxSpeed, player.vx));\n"
          "  if (axis === 0) {\n"
          "    player.vx = Math.max(0, clamped - friction * dt);\n"
          "  } else {\n"
          "    player.vx += axis * maxSpeed * dt;\n"
          "  }\n"
          "  player.x += player.vx * dt;\n"
          "}\n"
        )
        result=qa.review("horizontal movement",source)["rubric"]
        self.assertEqual(result["indicators_detected"],5)
        self.assertFalse(result["quality_approved"])
        self.assertFalse(result["behavior_verified"])

    def test_unrelated_task_needs_separate_tests(self):
        result=qa.review("Create an inventory menu", "function menu(){}")
        self.assertEqual(result["task_type"],"general")
        self.assertFalse(result["rubric"]["quality_approved"])

    def test_does_not_execute_arbitrary_code(self):
        malicious="require('child_process').execSync('shutdown /s');"
        result=qa.review("move horizontally",malicious)["rubric"]
        self.assertEqual(result["generated_code_executed"],False)
        self.assertEqual(result["indicators_detected"],0)

if __name__=="__main__":
    unittest.main()
