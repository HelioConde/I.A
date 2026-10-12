"""Real-user Luna intent regressions: no fabricated PC capabilities or searches.

Tests use injected fake tools only. They never touch a real user's PC,
browser, Downloads, model, disk writes or the public Internet.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.copilot_queries import copilot_answer
from brain_ssd.chat.server import ChatEngine
from brain_ssd.chat.current_affairs import needs_recent_public_sources


class DesktopFixture:
    screen_enabled = True
    def __init__(self, root: Path):
        self.roots = (root,)
        self.root = root
        self.reads = []
        self.previews = []
        self.system_calls = 0

    def status(self):
        return {
            "enabled": True, "files_enabled": True, "screen_enabled": True,
            "apps_enabled": True, "launch_enabled": True, "edit_enabled": True,
        }

    def system_info(self):
        self.system_calls += 1
        raise AssertionError("Router must not substitute PC hardware diagnosis")

    def list_directory(self, path):
        self.reads.append(path)
        if Path(path).name == "Downloads":
            return {
                "path": str(path), "truncated": False,
                "entries": [
                    {"name": "b.png", "type": "file"},
                    {"name": "a.jpg", "type": "file"},
                    {"name": "document.txt", "type": "file"},
                ],
            }
        return {
            "path": str(path), "truncated": False,
            "entries": [
                {"name": "Users", "type": "folder"},
                {"name": "Documents", "type": "folder"},
                {"name": "boot.ini", "type": "file"},
            ],
        }

    def preview_image(self, path):
        self.previews.append(path)
        return {"image_data_url": "data:image/jpeg;base64,YWJj",
                "vision_enabled": False}


class TestPastConversationRegression(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.fake = DesktopFixture(self.folder)

    def test_user_browser_tabs_question_does_not_guess(self):
        result = copilot_answer("Quais abas de navegador eu estou aberta ?", self.fake)
        self.assertEqual(result["local_action"], "copilot_browser_tabs_unsupported")
        self.assertIn("não consigo enumerar", result["answer"])
        self.assertEqual(self.fake.reads, [])

    def test_folder_question_lists_verified_folders_not_hardware(self):
        result = copilot_answer("Quais as principais pastas do meu pc ?", self.fake)
        self.assertEqual(result["local_action"], "copilot_folders")
        self.assertIn("Users", result["answer"])
        self.assertNotIn("boot.ini", result["answer"])
        self.assertEqual(self.fake.system_calls, 0)
        self.assertEqual(len(self.fake.reads), 1)

    def test_installed_games_do_not_claim_all_programs_are_games(self):
        result = copilot_answer("Quais jogos eu tenho instalado ?", self.fake)
        self.assertEqual(result["local_action"], "copilot_games_registry_limited")
        self.assertIn("não classifica", result["answer"])

    def test_pc_functions_return_capability_matrix(self):
        result = copilot_answer("Quais funções você consegue fazer no meu pc ?", self.fake)
        self.assertEqual(result["local_action"], "copilot_capabilities")
        self.assertIn("Edição de CÓDIGO", result["answer"])
        self.assertEqual(self.fake.system_calls, 0)

    def test_monitor_question_does_not_claim_vision(self):
        for question in (
            "Você consegue ver meu monitor 2 ?",
            "Você consegue ver meu monitor 1?",
            "Você consegue visualizar imagen ?",
        ):
            with self.subTest(question=question):
                result = copilot_answer(question, self.fake)
                self.assertIn(result["local_action"], (
                    "copilot_vision_limitation", "copilot_image_limitation"))
                self.assertIn("texto", result["answer"])
        self.assertEqual(self.fake.previews, [])

    def test_image_in_downloads_requires_authorized_listing_and_preview(self):
        with patch("brain_ssd.chat.copilot_queries.Path.home", return_value=self.folder):
            result = copilot_answer("Mostrar a primeira imagem no download", self.fake)
            self.assertEqual(result["local_action"], "copilot_image_preview")
            self.assertIn("a.jpg", result["answer"])
            self.assertEqual(self.fake.previews, [str(self.folder / "Downloads" / "a.jpg")])
            self.assertEqual(result["copilot_image_data_url"], "data:image/jpeg;base64,YWJj")
            listed = copilot_answer("localize imagen no download", self.fake)
            self.assertEqual(listed["local_action"], "copilot_downloads_list")
            self.assertIn("b.png", listed["answer"])

    def test_requests_to_write_txt_on_c_drive_never_claim_success(self):
        for question in (
            "você consegue criar um texto para mim no c:/",
            "crie o texto",
            "crie um arquivo txt na pasta C:/",
        ):
            with self.subTest(question=question):
                result = copilot_answer(question, self.fake)
                self.assertEqual(result["local_action"], "copilot_text_write_unsupported")
                self.assertIn("Nenhum arquivo foi criado", result["answer"])

    def test_plain_draft_is_still_for_the_llm(self):
        self.assertIsNone(copilot_answer("Crie um texto sobre minhas configurações", self.fake))

    def test_general_recent_news_includes_named_political_news(self):
        self.assertTrue(needs_recent_public_sources(
            "pesquise para mim sobre o Jair Bolsonaro mais recente notícias"))
        self.assertTrue(needs_recent_public_sources(
            "notícias recentes sobre Jair Bolsonaro"))
        self.assertFalse(needs_recent_public_sources(
            "Qual é a história do Jornal Nacional?"))

    def test_news_without_web_consent_never_calls_model(self):
        engine = ChatEngine(lambda: None)
        try:
            result = engine.ask("pesquise para mim sobre notícias recentes de Jair Bolsonaro", [])
            self.assertEqual(result["local_action"], "recent_news_permission")
            self.assertIn("Não fiz consulta externa", result["answer"])
            self.assertFalse(engine.status()["inference_verified"])
        finally:
            engine.close()

    def test_google_request_without_api_key_never_claims_it_searched(self):
        class MockWeb:
            provider = "auto"
            _serper_key = ""
            def search(self, question):
                raise AssertionError("Google must not be used without configuration")
        engine = ChatEngine(lambda: None, web_search_service=MockWeb())
        try:
            response = engine.ask(
                "utilizar as pesquisas do google sobre noticias jair bolsonaro", [],
                web_search=True)
            self.assertEqual(response["local_action"], "google_search_capability")
            self.assertIn("Nenhuma pesquisa Google foi realizada", response["answer"])
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
