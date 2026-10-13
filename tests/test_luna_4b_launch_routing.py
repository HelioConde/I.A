"""Qwen3-4B spoken-chat regression: never map generic requests to app launch.

Runs offline without models, microphone, Windows apps or network.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.copilot_queries import copilot_answer
from brain_ssd.chat.current_affairs import needs_recent_public_sources, time_sensitive_local_intent
from brain_ssd.chat.server import ChatEngine


class FakeCopilot:
    launch_enabled = True
    launch_without_confirmation = False
    def __init__(self):
        self.started = []
        self.offers = []

    def status(self):
        return {
            "enabled": True,
            "files_enabled": True,
            "screen_enabled": True,
            "apps_enabled": True,
            "launch_enabled": True,
            "edit_enabled": True,
        }

    def offer_launch(self, app_id):
        self.offers.append(app_id)
        return {"label": "Calculadora", "token": "fake-token", "app_id": app_id}

    def launch_by_name(self, name):
        self.started.append(name)
        raise AssertionError("Never launch a program while handling ordinary chat")


class LunaFourBIntents(unittest.TestCase):
    def setUp(self):
        self.copilot = FakeCopilot()

    def test_polite_news_date_and_general_questions_never_become_launch_info(self):
        ordinary = (
            "poderia me falar data de hoje",
            "poderia me dar as últimas notícias de hoje",
            "poderia me dar as últimas notícias de hoje",
            "Qual é a data de hoje?",
            "você consegue explicar o Qwen?",
            "pode explicar memória SSD?",
            "sabe o que é um modelo de linguagem?",
            "poderia abrir um arquivo de texto?",
        )
        for question in ordinary:
            with self.subTest(question=question):
                self.assertIsNone(copilot_answer(question, self.copilot))
        self.assertEqual(self.copilot.started, [])
        self.assertEqual(self.copilot.offers, [])

    def test_launch_questions_still_respond_about_launch_without_execution(self):
        for question in (
            "Você consegue abrir a Calculadora?",
            "Poderia iniciar o Chrome?",
            "Você pode abrir programas no meu computador?",
        ):
            with self.subTest(question=question):
                response = copilot_answer(question, self.copilot)
                self.assertEqual(response["local_action"], "copilot_launch_info")
                self.assertIn("Posso abrir aplicativos", response["answer"])
        self.assertEqual(self.copilot.started, [])
        self.assertEqual(self.copilot.offers, [])

    def test_explicit_open_still_requires_manual_confirmation(self):
        answer = copilot_answer("Abra a Calculadora", self.copilot)
        self.assertEqual(answer["local_action"], "copilot_launch_proposal")
        self.assertEqual(self.copilot.offers, ["calculator"])
        self.assertEqual(self.copilot.started, [])

    def test_natural_capability_question_is_grounded_in_permissions(self):
        for question in (
            "O que mais você consegue fazer",
            "Quais são suas funcionalidades?",
        ):
            with self.subTest(question=question):
                answer = copilot_answer(question, self.copilot)
                self.assertEqual(answer["local_action"], "copilot_capabilities")
                self.assertIn("Funções verificadas", answer["answer"])
                self.assertIn("Edição de CÓDIGO", answer["answer"])
        self.assertEqual(self.copilot.started, [])

    def test_local_date_queries_use_calendar_not_qwen(self):
        self.assertEqual(time_sensitive_local_intent("poderia me falar data de hoje"), "local_date")
        self.assertEqual(time_sensitive_local_intent("Qual é a data de hoje?"), "local_date")
        self.assertIsNone(time_sensitive_local_intent("notícias de hoje"))
        before = datetime.now().astimezone().date()
        engine = ChatEngine(lambda: None, copilot=self.copilot)
        try:
            chunks = []
            reply = engine.ask("poderia me falar data de hoje", [], on_chunk=chunks.append)
            after = datetime.now().astimezone().date()
            self.assertEqual(reply["local_action"], "local_date")
            self.assertEqual("".join(chunks), reply["answer"])
            self.assertTrue(any(str(year) in reply["answer"] for year in (before.year, after.year)))
            self.assertIn("relógio local", reply["answer"])
        finally:
            engine.close()
        self.assertEqual(self.copilot.started, [])

    def test_news_requires_opt_in_even_when_qwen_unavailable(self):
        question = "poderia me dar as últimas notícias de hoje"
        self.assertTrue(needs_recent_public_sources(question))
        engine = ChatEngine(lambda: None, copilot=self.copilot)
        try:
            result = engine.ask(question, [], web_search=False)
            self.assertEqual(result["local_action"], "recent_news_permission")
            self.assertIn("Pesquisar na web", result["answer"])
        finally:
            engine.close()
        self.assertEqual(self.copilot.started, [])


if __name__ == "__main__":
    unittest.main()
