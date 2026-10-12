"""Regressions from the 12/10 real Luna conversation, with no live Qwen."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.session_facts import (
    answer_session_fact, is_first_question_intent,
)
from brain_ssd.chat.server import ChatEngine
from brain_ssd.chat.history import ChatHistory


class SessionFactsTests(unittest.TestCase):
    def setUp(self):
        self.model = "Qwen3-0.6B-Q8_0.gguf"
        self.fake_clock = datetime(2026, 10, 12, 13, 21,
                                   tzinfo=timezone(timedelta(hours=-3)))

    def ask_local(self, question, history=None, first_question=None):
        return answer_session_fact(
            question, history or [], model_name=self.model,
            runtime_ready=True, first_question=first_question,
            clock=self.fake_clock,
        )

    def test_date_from_local_clock_not_llm(self):
        for question in ("Você sabe qual é a data de hoje?",
                         "Qual é a data atual?", "Que dia é hoje?"):
            with self.subTest(question=question):
                reply = self.ask_local(question)
                self.assertEqual(reply["local_action"], "local_current_date")
                self.assertIn("segunda-feira, 12 de outubro de 2026", reply["answer"])
                self.assertIn("UTC-03:00", reply["answer"])
                self.assertNotIn("não posso determinar", reply["answer"].casefold())

    def test_model_is_not_confused_with_project(self):
        reply = self.ask_local(
            "Qual modelo de inteligência artificial você está utilizando?")
        self.assertEqual(reply["local_action"], "local_model_identity")
        self.assertIn(self.model, reply["answer"])
        self.assertIn("Luna", reply["answer"])
        self.assertIn("Brain-SSD é o projeto", reply["answer"])

    def test_natural_how_are_you(self):
        reply = self.ask_local("Como você está hoje, Luna?")
        self.assertEqual(reply["local_action"], "local_assistant_status")
        self.assertIn("pronta para conversar", reply["answer"])

    def test_first_question_requires_sqlite_verified_oldest_message(self):
        self.assertTrue(is_first_question_intent(
            "Qual foi a primeira pergunta que fiz nesta conversa?"))
        with tempfile.TemporaryDirectory() as tmp:
            db = ChatHistory(Path(tmp) / "history.sqlite3")
            row = db.create()
            identity = row["id"]
            for i in range(18):
                first = "Olá, bom dia!" if i == 0 else "Pergunta " + str(i)
                db.append_exchange(identity, first, "Resposta " + str(i))
            # A small inference window cannot expose the original first question.
            history = db.recent_context(identity)
            self.assertNotIn("Olá, bom dia!", [x["content"] for x in history])
            self.assertEqual(db.first_user_question(identity), "Olá, bom dia!")
            engine = ChatEngine(lambda: None)
            try:
                result = engine.ask(
                    "Qual foi a primeira pergunta que fiz nesta conversa?",
                    history, first_question=db.first_user_question(identity),
                )
                self.assertEqual(result["local_action"], "local_first_question")
                self.assertIn("Olá, bom dia!", result["answer"])
            finally:
                engine.close()

    def test_missing_first_question_never_invents_it(self):
        reply = self.ask_local("Qual foi a primeira pergunta que fiz nesta conversa?",
                               [{"role": "user", "content": "Pergunta recente"}])
        self.assertEqual(reply["local_action"], "local_first_question_unavailable")
        self.assertNotIn("Pergunta recente", reply["answer"])

    def test_last_five_messages_are_role_correct_and_in_order(self):
        history = [{"role": "user" if i % 2 == 0 else "assistant",
                    "content": "Mensagem " + str(i)} for i in range(12)]
        reply = self.ask_local("Resuma as últimas cinco mensagens que trocamos.", history)
        self.assertEqual(reply["local_action"], "local_recent_messages")
        self.assertNotIn("Mensagem 6", reply["answer"])
        for i in range(7, 12):
            self.assertIn("Mensagem " + str(i), reply["answer"])
        self.assertLess(reply["answer"].index("Mensagem 7"),
                        reply["answer"].index("Mensagem 11"))

    def test_empty_history_reports_unavailability(self):
        reply = self.ask_local("Resuma as últimas cinco mensagens que trocamos.")
        self.assertEqual(reply["local_action"], "local_recent_messages_unavailable")

    def test_history_memory_distinction(self):
        reply = self.ask_local(
            "Você consegue lembrar o que conversamos anteriormente?",
            [{"role": "user", "content": "Bom dia."}],
        )
        self.assertEqual(reply["local_action"], "local_history_capability")
        self.assertIn("SQLite", reply["answer"])
        self.assertIn("diferente das lembranças episódicas", reply["answer"])

    def test_ambiguous_daily_information_asks_which_topic(self):
        from brain_ssd.chat.current_affairs import time_sensitive_local_intent
        text = "Quais informações de hoje você consegue me fornecer?"
        self.assertEqual(time_sensitive_local_intent(text), "ambiguous_today")
        engine = ChatEngine(lambda: None)
        try:
            reply = engine.ask(text, [])
            self.assertEqual(reply["local_action"], "today_topic_clarification")
            self.assertIn("Diga o assunto", reply["answer"])
        finally:
            engine.close()

    def test_do_not_intercept_unrelated_model_or_weather_questions(self):
        for question in (
            "Como quantizar um modelo Qwen?",
            "Quero um modelo de arquivo HTML.",
            "Como está o clima hoje em Brasília?",
            "Você lembra o que é um tokenizador?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(self.ask_local(question))

    def test_state_is_available_without_loading_qwen(self):
        engine = ChatEngine(lambda: None)
        try:
            a = engine.ask("Você sabe qual é a data de hoje?", [])
            b = engine.ask("Qual modelo de inteligência artificial você está utilizando?", [])
            c = engine.ask("Como você está hoje, Luna?", [])
            self.assertEqual(a["local_action"], "local_current_date")
            self.assertEqual(b["local_action"], "local_model_identity")
            self.assertEqual(c["local_action"], "local_assistant_status")
            self.assertFalse(engine.status()["inference_verified"])
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
