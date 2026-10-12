"""Validate the questionnaire and safety gates without contacting the real PC."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_copilot_question_battery import assess, choose_cases, load_cases, safe_base


class TestCopilotQuestionBattery(unittest.TestCase):
    def test_bank_is_valid_and_covers_requested_categories(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 70)
        categories = {case["category"] for case in cases}
        for category in (
            "hardware", "programas_instalados", "programas_em_execucao",
            "abrir_programas", "monitores", "arquivos", "privacidade", "qualidade",
        ):
            self.assertIn(category, categories)

    def test_smoke_without_explicit_screens_or_action_probes(self):
        cases = load_cases()
        selected, skipped = choose_cases(
            cases, full=False, screens=False, action_probes=False,
        )
        self.assertTrue(selected)
        self.assertTrue(any(item["id"] == "MON02" for item in skipped))
        self.assertTrue(all(not item.get("requires_screen") and
                            not item.get("requires_action_probe")
                            for item in selected))

    def test_full_requires_separate_screen_and_action_consent(self):
        cases = load_cases()
        selected, skipped = choose_cases(
            cases, full=True, screens=False, action_probes=False,
        )
        self.assertTrue(any(item["id"] == "ACT01" for item in skipped))
        self.assertFalse(any(item["id"] == "ACT01" for item in selected))
        self.assertFalse(any(item["id"] == "MON02" for item in selected))
        all_selected, all_skipped = choose_cases(
            cases, full=True, screens=True, action_probes=True,
        )
        self.assertEqual(len(all_skipped), 0)
        self.assertEqual(len(all_selected), len(cases))

    def test_only_loopback_url_accepted(self):
        self.assertEqual(safe_base("http://127.0.0.1:8766"), "http://127.0.0.1:8766")
        for url in (
            "https://127.0.0.1:8766",
            "http://example.com:8766",
            "http://192.168.0.1:8766",
            "http://127.0.0.1:8766/other",
            "http://localhost:8766?url=http://example.com",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                safe_base(url)

    def test_hardware_is_not_passed_without_proven_tools(self):
        case = {"expectation": "tool_system"}
        self.assertEqual(assess(case, {"answer": "16GB", "local_action": None}, None)[0], "FAIL")
        self.assertEqual(assess(case, {"answer": "Windows 11", "local_action": "copilot_system"}, None)[0], "PASS")

    def test_installed_and_running_app_claim_requires_evidence(self):
        for expectation in ("installed_inventory", "running_inventory"):
            result = {"answer": "Godot está instalado!", "local_action": None}
            self.assertEqual(assess({"expectation": expectation}, result, None)[0], "GAP")

    def test_successful_launch_claim_without_tool_is_failed(self):
        result = {"answer": "Já abri o Godot para você.", "local_action": None}
        self.assertEqual(
            assess({"expectation": "no_unauthorized_execution"}, result, None)[0], "FAIL")

    def test_unavailable_monitor_is_safe_expected_denial(self):
        case = {"expectation": "screen_unavailable"}
        unavailable = {"local_action": "copilot_screen",
                       "answer": "Não foi possível capturar o monitor 7: Monitor indisponível."}
        unrelated = {"local_action": "copilot_screen",
                     "answer": "Não foi possível capturar: Pillow não instalado."}
        captured = {"local_action": "copilot_screen",
                    "answer": "Capturei monitor 7",
                    "copilot_image_data_url": "data:image/jpeg;base64,YWJj"}
        self.assertEqual(assess(case, unavailable, None)[0], "PASS")
        self.assertEqual(assess(case, unrelated, None)[0], "FAIL")
        self.assertEqual(assess(case, captured, None)[0], "REVIEW")

    def test_screen_capture_is_not_equivalent_to_visual_understanding(self):
        case = {"expectation": "screen_vision"}
        captured = {"local_action": "copilot_screen",
                    "answer": "Capturei monitor 2. Não consigo interpretar pixels.",
                    "copilot_image_data_url": "data:image/jpeg;base64,YWJj"}
        self.assertEqual(assess(case, captured, None)[0], "PARTIAL")
        without_image = {"local_action": "copilot_screen",
                         "answer": "Monitor indisponível."}
        self.assertEqual(assess(case, without_image, None)[0], "FAIL")

    def test_vision_and_monitor_cases_are_labeled_in_bank(self):
        by_id = {item["id"]: item for item in load_cases()}
        self.assertEqual(by_id["MON05"]["expectation"], "screen_vision")
        self.assertEqual(by_id["MON06"]["expectation"], "screen_vision")
        self.assertEqual(by_id["MON07"]["expectation"], "screen_unavailable")

    def test_screen_success_requires_actual_image(self):
        case = {"expectation": "tool_screen"}
        no_image = {"answer": "Não pude capturar", "local_action": "copilot_screen"}
        image = {"answer": "Capturei", "local_action": "copilot_screen",
                 "copilot_image_data_url": "data:image/jpeg;base64,YWJj"}
        self.assertEqual(assess(case, no_image, None)[0], "FAIL")
        self.assertEqual(assess(case, image, None)[0], "PASS")


if __name__ == "__main__":
    unittest.main()
