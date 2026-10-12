"""Tool-routing regression: explicit PC/screen requests are never Qwen guesses."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.copilot import CopilotPermissionError
from brain_ssd.chat.copilot_queries import copilot_answer
from brain_ssd.chat.server import ChatEngine


class FakeCopilot:
    screen_enabled = True

    def __init__(self):
        self.captured = []
        self.window_queries = []
        self.info_calls = 0

    def status(self):
        return {"enabled": True}

    def system_info(self):
        self.info_calls += 1
        return {
            "os": "Windows 11", "architecture": "AMD64",
            "cpu_name": "CPU fictícia", "cpu_threads": 8,
            "ram_total_gib": 16.0,
            "disks": [{"root": "C:\\", "free_gib": 200.0, "total_gib": 500.0}],
            "python": "3.14.7",
        }

    def capture_screen(self, monitor):
        self.captured.append(monitor)
        return {"image_data_url": "data:image/jpeg;base64,YWJj"}

    def list_monitor_windows(self, monitor):
        self.window_queries.append(monitor)
        return [{"title": "Godot Editor"}, {"title": "Visual Studio Code"}]


class TestCopilotQuestionRouter(unittest.TestCase):
    def test_computer_facts_from_tool_not_qwen(self):
        fake = FakeCopilot()
        r = copilot_answer("O que você sabe sobre meu computador?", fake)
        self.assertEqual(r["local_action"], "copilot_system")
        self.assertIn("16.0 GiB", r["answer"])
        self.assertIn("CPU fictícia", r["answer"])
        self.assertEqual(fake.info_calls, 1)
        self.assertEqual(fake.captured, [])

    def test_screen_two_lists_actual_windows_and_preview(self):
        fake = FakeCopilot()
        r = copilot_answer("Olhe para o meu monitor 2, identifique os programas abertos", fake)
        self.assertEqual(r["local_action"], "copilot_screen")
        self.assertEqual(fake.captured, [2])
        self.assertEqual(fake.window_queries, [2])
        self.assertIn("Godot Editor", r["answer"])
        self.assertIn("Visual Studio Code", r["answer"])
        self.assertEqual(r["copilot_image_data_url"], "data:image/jpeg;base64,YWJj")
        self.assertNotIn("interpretei o texto", r["answer"].lower())

    def test_godot_request_does_not_fabricate_diagnosis(self):
        fake = FakeCopilot()
        r = copilot_answer(
            "Olhe para meu monitor 2, identifique o erro no Godot, "
            "encontre o arquivo relacionado e me explique a correção.", fake)
        self.assertEqual(fake.captured, [2])
        self.assertIn("OCR local indisponível", r["answer"])
        self.assertIn("OCR", r["answer"])

    def test_screen_godot_uses_requested_ocr_when_available(self):
        fake = FakeCopilot()
        frames = []
        def ocr(monitor, *, screenshot):
            frames.append((monitor, screenshot))
            return {"text": "SCRIPT ERROR: res://scripts/player.gd:42",
                    "language": "eng"}
        fake.read_screen_text = ocr
        result = copilot_answer(
            "Olhe para o meu monitor 2 e identifique o erro no Godot", fake)
        self.assertEqual(fake.captured, [2])
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0][0], 2)
        self.assertIn("res://scripts/player.gd:42", result["answer"])
        self.assertIn("OCR local", result["answer"])

    def test_no_screen_permission(self):
        fake = FakeCopilot()
        fake.screen_enabled = False
        r = copilot_answer("Olhe para o monitor 1 e veja os programas abertos", fake)
        self.assertEqual(r["local_action"], "copilot_screen_disabled")
        self.assertEqual(fake.captured, [])
        self.assertNotIn("copilot_image_data_url", r)

    def test_capture_failure_does_not_fabricate_image(self):
        fake = FakeCopilot()
        def error(monitor):
            raise CopilotPermissionError("Monitor indisponível.")
        fake.capture_screen = error
        r = copilot_answer("Olhe para o monitor 3, identifique os programas abertos", fake)
        self.assertIn("Não foi possível capturar", r["answer"])
        self.assertNotIn("copilot_image_data_url", r)

    def test_unrelated_question_is_regular_model_work(self):
        fake = FakeCopilot()
        self.assertIsNone(copilot_answer("O que você sabe sobre o Microsoft Copilot?", fake))
        self.assertIsNone(copilot_answer("Como montar um computador gamer?", fake))
        self.assertIsNone(copilot_answer("Quero aprender Godot.", fake))
        self.assertEqual(fake.captured, [])

    def test_disabled_session_is_truthful(self):
        r = copilot_answer("O que você sabe sobre meu computador?", None)
        self.assertEqual(r["local_action"], "copilot_disabled")
        self.assertIn("não está habilitado", r["answer"])

    def test_route_works_even_during_model_startup(self):
        fake = FakeCopilot()
        engine = ChatEngine(lambda: None, copilot=fake)
        try:
            r = engine.ask("O que você sabe sobre meu computador?", [])
            self.assertEqual(r["local_action"], "copilot_system")
            self.assertFalse(engine.status()["inference_verified"])
        finally:
            engine.close()

    def test_local_pc_does_not_trigger_web_or_model(self):
        fake = FakeCopilot()
        engine = ChatEngine(lambda: None, copilot=fake)
        chunks = []
        try:
            r = engine.ask("Olhe para o monitor 1, identifique os programas abertos", [],
                           on_chunk=chunks.append, web_search=False)
            self.assertEqual(r["answer"], "".join(chunks))
            self.assertFalse(engine.status()["inference_verified"])
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
