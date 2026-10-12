"""Real-user Luna follow-ups: no fictitious tabs/weather, no clipped HUD cards.

No Windows hardware, network, browser or GGUF is used by this suite.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.copilot_queries import copilot_answer, _grounded_desktop_question
from brain_ssd.chat.current_affairs import time_sensitive_local_intent
from brain_ssd.chat.local_actions import local_command
from brain_ssd.chat.server import ChatEngine


class FakeRuntime:
    def close(self):
        pass


class NoArchive:
    def retrieve(self, *args, **kwargs):
        raise AssertionError("Greetings must not retrieve unrelated wiki sources")


class FakeWeb:
    provider = "auto"


class LunaHudTrustFollowupTests(unittest.TestCase):
    def test_my_open_browser_tabs_never_fall_through_to_qwen(self):
        for question in (
            "você consegue ver qual abas as minhas estão abertas",
            "Quais são as minhas abas abertas no Google Chrome?",
            "mas isso que você mandou não é as abas e sim os programas",
        ):
            with self.subTest(question=question):
                result = copilot_answer(question, None)
                self.assertEqual(result["local_action"], "copilot_browser_tabs_unsupported")
                self.assertIn("não consigo enumerá-las", result["answer"])
                self.assertIn("PROCESSOS", result["answer"])

    def test_browser_tab_explanations_not_intercepted(self):
        for question in (
            "O que são abas do navegador?",
            "Como organizar abas do Chrome?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(_grounded_desktop_question(question, None))

    def test_unclear_transcription_about_open_chrome_prompts_clarification(self):
        result = copilot_answer(
            "verifique para micose tão aberto no Google Chrome", None)
        self.assertEqual(result["local_action"], "copilot_browser_intent_clarification")
        self.assertIn("ABAS", result["answer"])
        self.assertIn("PROCESSOS", result["answer"])

    def test_real_process_inventory_remains_accessible(self):
        self.assertIsNone(_grounded_desktop_question(
            "Mostre os processos ativos do Chrome", None))

    def test_windows_capability_without_inspection_does_not_claim_to_see(self):
        result = copilot_answer(
            "você consegue ver o que que tá aberto meu computador", None)
        self.assertEqual(result["local_action"], "copilot_windows_capability")
        self.assertIn("não verifiquei", result["answer"].casefold())

    def test_compound_greetings_do_not_need_cached_wikipedia(self):
        for question in ("Olá bom dia", "Olá, bom dia!", "Oi boa tarde"):
            with self.subTest(question=question):
                result = local_command(question, None)
                self.assertEqual(result["local_action"], "greeting")
                self.assertIn("Em que posso ajudar?", result["answer"])
        engine = ChatEngine(FakeRuntime, web_knowledge=NoArchive())
        engine.start()
        try:
            response = engine.ask("Olá bom dia", [])
            self.assertEqual(response["local_action"], "greeting")
            self.assertNotIn("web_sources", response)
        finally:
            engine.close()

    def test_live_weather_intent_requires_real_data_not_the_language_model(self):
        self.assertEqual(
            time_sensitive_local_intent("Qual vai ser o clima em Brasília hoje?"),
            "live_weather")
        self.assertEqual(
            time_sensitive_local_intent("Como está o tempo em Brasília agora?"),
            "live_weather")
        self.assertIsNone(
            time_sensitive_local_intent("Explique o clima tropical no Brasil."))
        self.assertIsNone(
            time_sensitive_local_intent("O que é previsão do tempo?"))
        self.assertEqual(
            time_sensitive_local_intent("Qual a previsão do tempo em Brasília?"),
            "live_weather")
        engine = ChatEngine(lambda: None)
        try:
            answer = engine.ask("Qual vai ser o clima em Brasília hoje", [])
            self.assertEqual(answer["local_action"], "weather_provider_unavailable")
            self.assertIn("não há um provedor", answer["answer"])
            self.assertFalse(engine.status()["inference_verified"])
        finally:
            engine.close()

    def test_even_search_consent_does_not_pretend_weather_provider_exists(self):
        engine = ChatEngine(lambda: None, web_search_service=FakeWeb())
        try:
            answer = engine.ask("Qual vai ser o clima em Brasília hoje", [],
                                web_search=True)
            self.assertEqual(answer["local_action"], "weather_provider_unavailable")
            self.assertIn("Não consultei", answer["answer"])
        finally:
            engine.close()

    def test_vague_today_requests_request_topic_clarification(self):
        for question in (
            "Quais as informações de hoje",
            "O que tem de novo hoje?",
        ):
            with self.subTest(question=question):
                engine = ChatEngine(lambda: None)
                try:
                    answer = engine.ask(question, [])
                    self.assertEqual(answer["local_action"], "today_topic_clarification")
                    self.assertIn("notícias", answer["answer"])
                finally:
                    engine.close()

    def test_hud_card_layout_is_not_allowed_to_flex_shrink(self):
        css = (ROOT / "chat" / "luna-hud.css").read_text(encoding="utf-8")
        self.assertIn(".luna-rail-head,.luna-rail-end,.luna-hud-card", css)
        self.assertIn("flex:0 0 auto;", css)
        self.assertIn(".luna-hud-card {min-height:max-content;}", css)
        self.assertIn("overflow-y:auto;", css)
        self.assertIn(".sidebar {min-height:0;overflow-y:auto;", css)


if __name__ == "__main__":
    unittest.main()
